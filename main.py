import openai
from flask import Flask, request, jsonify, Response
import json
import time
import logging
from logging.handlers import RotatingFileHandler
import sys
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[
                        RotatingFileHandler("middleware.log", maxBytes=10000, backupCount=1),
                        logging.StreamHandler(sys.stdout)
                    ])

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure OpenAI client to point to LM Studio
openai.api_base = "http://localhost:1234/v1"
openai.api_key = "lm-studio"

# Templates (unchanged)
BREAKDOWN_TEMPLATE = """
User Prompt: "{user_prompt}"
Reflect on the query. Assume the most straightforward interpretation unless explicitly told otherwise. Avoid using code or outside services unless it is a coding problem.
Provide a number of steps from 1 up to 5 based on the complexity of the problem. Use as few steps as necessary to resolve the task.
Respond only with the numbered list of steps, nothing else.
"""

STEP_PROCESSING_TEMPLATE = """
Original User Prompt: "{user_prompt}"
Steps: {steps}

Your task is to perform Step {step_number}: {step_description}

Provide a concise solution for this specific step by thinking out loud and giving your chain of thought. Reflect and reason out loud and check your own work.
"""

SYNTHESIS_TEMPLATE = """
Original User Prompt: "{user_prompt}"
Step-by-Step Responses:
{step_responses}

Do a sanity check. Analyze these steps for coherent logic and give your thoughts step by step, then synthesize a final concise answer when done analyzing and only include the final polished answer.
"""

# Define function to count tokens
def count_tokens(text):
    # Simple token estimation by splitting on whitespace
    return len(text.split())

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def send_prompt_to_lm_studio(prompt, max_tokens=None, stream=False):
    try:
        # Build the payload without the 'model' field
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,  # Reduced temperature for less randomness
            "stream": stream
        }

        # Include 'max_tokens' only if it's specified
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        response = requests.post(
            f"{openai.api_base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {openai.api_key}"},
            stream=stream
        )
        response.raise_for_status()

        if stream:
            # Handle streaming response
            return response.iter_lines()
        else:
            # Handle non-streaming response
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                message = data['choices'][0].get('message', {})
                content = message.get('content', '')
                return content.strip()
            else:
                logger.error(f"No choices found in response: {data}")
                return ""
    except requests.RequestException as e:
        logger.error(f"Error sending prompt to LM Studio: {e}")
        raise

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    logger.info(f"Received POST request to /v1/chat/completions from {request.remote_addr}")
    request_data = request.json
    messages = request_data.get('messages', [])

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    user_prompt = messages[-1].get('content', '')
    logger.info(f"Received prompt: {user_prompt}")

    try:
        # Step 1: Get task breakdown (with adjusted token limit)
        breakdown_prompt = BREAKDOWN_TEMPLATE.format(user_prompt=user_prompt)
        steps_text = send_prompt_to_lm_studio(breakdown_prompt, max_tokens=500, stream=False)
        if not steps_text:
            return jsonify({"error": "Failed to get task breakdown from LM Studio"}), 500

        # Step 2: Process each step (with adjusted token limit)
        steps = steps_text.strip().split('\n')
        step_responses = []
        for i, step in enumerate(steps, 1):
            step_number = i
            if '. ' in step:
                _, step_description = step.split('. ', 1)
            else:
                step_description = step

            step_prompt = STEP_PROCESSING_TEMPLATE.format(
                user_prompt=user_prompt,
                steps=steps_text,
                step_number=step_number,
                step_description=step_description
            )
            step_response = send_prompt_to_lm_studio(step_prompt, max_tokens=500, stream=False)
            if step_response:
                step_responses.append(f"Step {i}: {step_description}\nResponse: {step_response}\n")

        # Step 3: Synthesize final answer with dynamic max_tokens
        synthesis_prompt = SYNTHESIS_TEMPLATE.format(
            user_prompt=user_prompt,
            step_responses="\n".join(step_responses)
        )

        # Implement dynamic max_tokens based on token count
        MAX_CONTEXT_LENGTH = 4096  # Assuming the model's maximum context length is 2048 tokens

        # Estimate tokens used in the synthesis prompt
        prompt_tokens = count_tokens(synthesis_prompt)

        # Reserve some tokens for the response (e.g., 50 tokens for safety)
        available_tokens = MAX_CONTEXT_LENGTH - prompt_tokens - 50

        # Ensure available_tokens is within reasonable bounds
        available_tokens = max(min(available_tokens, 4096), 500)

        logger.info(f"Calculated available tokens for synthesis: {available_tokens}")

        # Stream the final synthesized answer back to AnythingLLM
        def generate():
            try:
                response_lines = send_prompt_to_lm_studio(
                    synthesis_prompt, max_tokens=available_tokens, stream=True
                )
                response_text = ""
                for line in response_lines:
                    if line:
                        line = line.decode('utf-8')
                        logger.debug(f"Received line: {line}")
                        if line.startswith('data: '):
                            data = json.loads(line[6:])
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    response_text += content
                                    yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
                # Optionally, check if the response seems incomplete
                if not response_text.strip().endswith('.'):
                    logger.warning("Response may be incomplete due to token limit.")
                # Send the stop signal
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error streaming final response: {e}", exc_info=True)
                yield "data: [DONE]\n\n"

        return Response(generate(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"An error occurred during processing: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

if __name__ == '__main__':
    logger.info("Starting LM Studio Middleware")
    logger.info("Server will be accessible at:")
    logger.info("http://localhost:5000/v1")
    logger.info("http://127.0.0.1:5000/v1")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
