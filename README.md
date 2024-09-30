# ChainOfThought-Adapter

**ChainOfThought-Adapter** is a simple middleware built with Flask that connects to LM Studio (or any local language model) to process complex user requests using a "Chain of Thought" method. This project started because I couldn't find a good way to use Chain of Thought reasoning with LM Studio.

The middleware acts as a smart bridge, breaking down user questions into logical steps, handling each step separately, and then putting together a clear final response. While it was made for personal use, it can help anyone interested in structured prompt processing.

## Attribution

Inspired by ReflectionAnyLLM (https://github.com/antibitcoin/ReflectionAnyLLM) and PyThoughtChain (https://github.com/devinambron/PyThoughtChain)

## Features

- **Quick & Simple Implementation**: Designed for fast prototyping of a Chain of Thought solution with minimal setup.
- **Task Breakdown**: Automatically divides complex requests into logical numbered steps.
- **Sequential Processing**: Handles each step separately, reflecting and reasoning at each stage.
- **Final Synthesis**: Checks all steps and gives a clear, well-reasoned answer.
- **Dynamic Token Management**: Adjusts token allocation based on context size to improve response quality.
- **Error Handling & Retry Logic**: Includes basic error handling with a retry mechanism.

## Architecture

The middleware has three main stages:

1. **Task Breakdown**: Uses a template to understand the user's prompt and lists the steps.
2. **Step Processing**: Each step is processed separately, where the model thinks and reasons out loud before answering.
3. **Synthesis**: Analyzes all step responses together to produce a final coherent answer.

## Installation

### Clone the Repository

```bash
git clone https://github.com/yourusername/ChainOfThought-Adapter.git
cd ChainOfThought-Adapter
```

### Install Dependencies
Make sure to use the `openai` module version 0.28.0. This middleware is tested only with this version, so other versions may not work.

```bash
pip install -r requirements.txt
```

### Configure LM Studio
Set up LM Studio on your local machine and ensure the API endpoint (http://localhost:1234/v1) is accessible. Update `openai.api_base` in the code if you're using a different endpoint.

### Run the Middleware

```bash
python main.py
```

### Access the Service
Once the middleware is running, you can access it at:

```
http://localhost:5000/v1/chat/completions
```

## Usage
Send a POST request to the `/v1/chat/completions` endpoint with this payload:

```json
{
  "messages": [
    {"role": "user", "content": "Explain the significance of quantum computing in modern cryptography."}
  ]
}
```

The response will include a structured breakdown of the query, step-by-step outputs, and a final synthesized answer.

## Contributing
Contributions are welcome! Feel free to submit a pull request or open an issue for feature requests or bug reports. Since this is a simple implementation, there's plenty of room for improvements.

## License
This project is licensed under the GNU General Public License v3.0.
