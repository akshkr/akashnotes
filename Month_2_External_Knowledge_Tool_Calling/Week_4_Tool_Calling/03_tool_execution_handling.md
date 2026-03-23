# Parsing Tool Calls, Executing Functions & Returning Results

The LLM has decided to call your function. Now what? This guide covers the complete flow: parsing the tool call, executing your Python function, and returning the result back to the LLM.

---

## The Tool Calling Flow

```mermaid
sequenceDiagram
    participant U as User
    participant L as LLM
    participant A as Your App
    participant F as Function

    U->>L: "What's the weather in Tokyo?"
    L->>A: tool_call: get_weather(city="Tokyo")
    A->>F: Execute get_weather("Tokyo")
    F->>A: {"temp": 22, "condition": "sunny"}
    A->>L: tool_result: {"temp": 22, ...}
    L->>U: "It's 22°C and sunny in Tokyo!"
```

---

## Step 1: Detect Tool Calls

When the LLM wants to call a function, it returns a special response:

```python
from openai import OpenAI
import json

client = OpenAI()

# Define your tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["city"]
            }
        }
    }
]

# Make the API call
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools
)

message = response.choices[0].message

# Check if LLM wants to call a tool
if message.tool_calls:
    print("LLM wants to call tools!")
    for tool_call in message.tool_calls:
        print(f"  Function: {tool_call.function.name}")
        print(f"  Arguments: {tool_call.function.arguments}")
else:
    print("No tool calls, regular response:", message.content)
```

---

## Step 2: Parse the Tool Call

Extract the function name and arguments:

```python
def parse_tool_call(tool_call) -> dict:
    """
    Parse a tool call from the LLM response.

    Returns:
        dict with 'id', 'name', and 'arguments'
    """
    return {
        "id": tool_call.id,
        "name": tool_call.function.name,
        "arguments": json.loads(tool_call.function.arguments)
    }

# Usage
if message.tool_calls:
    for tool_call in message.tool_calls:
        parsed = parse_tool_call(tool_call)
        print(f"Call ID: {parsed['id']}")
        print(f"Function: {parsed['name']}")
        print(f"Arguments: {parsed['arguments']}")
```

---

## Step 3: Execute the Function

Map function names to actual Python functions and execute:

```python
# Define your actual functions
def get_weather(city: str, unit: str = "celsius") -> dict:
    """Get weather for a city (mock implementation)."""
    # In real code, call a weather API
    weather_data = {
        "Tokyo": {"temp": 22, "condition": "sunny"},
        "London": {"temp": 15, "condition": "cloudy"},
        "New York": {"temp": 18, "condition": "rainy"}
    }

    data = weather_data.get(city, {"temp": 20, "condition": "unknown"})

    if unit == "fahrenheit":
        data["temp"] = data["temp"] * 9/5 + 32

    data["unit"] = unit
    data["city"] = city
    return data

def search_web(query: str) -> str:
    """Search the web (mock implementation)."""
    return f"Search results for: {query}"

# Function registry
FUNCTIONS = {
    "get_weather": get_weather,
    "search_web": search_web
}

def execute_function(name: str, arguments: dict) -> any:
    """Execute a function by name with given arguments."""

    if name not in FUNCTIONS:
        raise ValueError(f"Unknown function: {name}")

    func = FUNCTIONS[name]
    return func(**arguments)

# Usage
result = execute_function("get_weather", {"city": "Tokyo", "unit": "celsius"})
print(result)  # {"temp": 22, "condition": "sunny", "unit": "celsius", "city": "Tokyo"}
```

---

## Step 4: Return Results to the LLM

Send the function result back so the LLM can formulate a response:

```python
def complete_tool_call(client, messages: list, tools: list) -> str:
    """
    Complete the full tool calling cycle.

    Returns the final text response from the LLM.
    """

    # Step 1: Initial request
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=tools
    )

    message = response.choices[0].message

    # Step 2: Check for tool calls
    if not message.tool_calls:
        return message.content

    # Step 3: Add assistant message to history
    messages.append(message)

    # Step 4: Execute each tool call and add results
    for tool_call in message.tool_calls:
        parsed = parse_tool_call(tool_call)

        try:
            # Execute the function
            result = execute_function(parsed["name"], parsed["arguments"])
            result_str = json.dumps(result)
        except Exception as e:
            result_str = json.dumps({"error": str(e)})

        # Add tool result to messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result_str
        })

    # Step 5: Get final response from LLM
    final_response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=tools
    )

    return final_response.choices[0].message.content

# Usage
messages = [{"role": "user", "content": "What's the weather in Tokyo?"}]
answer = complete_tool_call(client, messages, tools)
print(answer)  # "The current weather in Tokyo is 22°C and sunny!"
```

---

## Complete Example: Multi-Tool Agent

```python
from openai import OpenAI
import json
from datetime import datetime

client = OpenAI()

# Define multiple tools
def get_weather(city: str) -> dict:
    """Get weather for a city."""
    return {"city": city, "temp": 22, "condition": "sunny"}

def get_time(timezone: str = "UTC") -> dict:
    """Get current time in a timezone."""
    return {"timezone": timezone, "time": datetime.now().isoformat()}

def calculate(expression: str) -> dict:
    """Evaluate a math expression."""
    try:
        result = eval(expression)  # Note: Use safer evaluation in production!
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}

# Tool registry
TOOLS = {
    "get_weather": get_weather,
    "get_time": get_time,
    "calculate": calculate
}

# Tool schemas
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current time in a timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone name"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a mathematical expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression"}
                },
                "required": ["expression"]
            }
        }
    }
]

class ToolAgent:
    """Agent that can use multiple tools."""

    def __init__(self):
        self.client = OpenAI()
        self.messages = []

    def chat(self, user_message: str) -> str:
        """Process a user message, potentially using tools."""

        self.messages.append({"role": "user", "content": user_message})

        # Keep processing until we get a final response
        while True:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=self.messages,
                tools=TOOL_SCHEMAS
            )

            message = response.choices[0].message

            # No tool calls - we have our answer
            if not message.tool_calls:
                self.messages.append(message)
                return message.content

            # Process tool calls
            self.messages.append(message)

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                print(f"  [Calling {name}({args})]")

                # Execute tool
                if name in TOOLS:
                    result = TOOLS[name](**args)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                # Add result to messages
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

# Usage
agent = ToolAgent()

print(agent.chat("What's the weather in Paris?"))
print()
print(agent.chat("What's 15% of 230?"))
print()
print(agent.chat("What time is it in Tokyo timezone?"))
```

---

## Handling Multiple Tool Calls

The LLM might want to call multiple tools at once:

```python
def handle_parallel_tool_calls(message, functions: dict) -> list:
    """
    Handle multiple tool calls from a single LLM response.

    Returns list of tool results to send back.
    """
    results = []

    for tool_call in message.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        try:
            if name in functions:
                result = functions[name](**args)
            else:
                result = {"error": f"Function {name} not found"}
        except Exception as e:
            result = {"error": str(e)}

        results.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result)
        })

    return results

# Example: LLM calls both get_weather and get_time
# Response would contain two tool_calls
# We process both and return both results
```

```mermaid
flowchart TB
    A["LLM Response"] --> B{{"Multiple tool_calls?"}}
    B -->|Yes| C["Process in parallel"]
    B -->|No| D["Process single call"]

    C --> E["Tool 1 Result"]
    C --> F["Tool 2 Result"]
    C --> G["Tool 3 Result"]

    E --> H["Combine Results"]
    F --> H
    G --> H

    D --> I["Single Result"]

    H --> J["Send back to LLM"]
    I --> J
```

---

## Error Handling

Always handle errors gracefully:

```python
def safe_execute_tool(name: str, args: dict, functions: dict) -> dict:
    """
    Safely execute a tool with comprehensive error handling.
    """

    # Check if function exists
    if name not in functions:
        return {
            "success": False,
            "error": f"Unknown function: {name}",
            "error_type": "function_not_found"
        }

    func = functions[name]

    try:
        # Validate arguments against function signature
        import inspect
        sig = inspect.signature(func)

        # Check for missing required arguments
        for param_name, param in sig.parameters.items():
            if param.default == inspect.Parameter.empty:
                if param_name not in args:
                    return {
                        "success": False,
                        "error": f"Missing required argument: {param_name}",
                        "error_type": "missing_argument"
                    }

        # Execute the function
        result = func(**args)

        return {
            "success": True,
            "result": result
        }

    except TypeError as e:
        return {
            "success": False,
            "error": f"Invalid arguments: {str(e)}",
            "error_type": "invalid_arguments"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "error_type": "execution_error"
        }

# Usage
result = safe_execute_tool("get_weather", {"city": "Tokyo"}, TOOLS)

if result["success"]:
    print(f"Result: {result['result']}")
else:
    print(f"Error ({result['error_type']}): {result['error']}")
```

---

## Anthropic Tool Calling

Anthropic uses a slightly different format:

```python
from anthropic import Anthropic

client = Anthropic()

# Define tools in Anthropic format
tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
        }
    }
]

# Make request
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}]
)

# Check for tool use
for block in response.content:
    if block.type == "tool_use":
        print(f"Tool: {block.name}")
        print(f"Input: {block.input}")
        print(f"ID: {block.id}")

        # Execute and return result
        result = get_weather(**block.input)

        # Continue conversation with tool result
        follow_up = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            tools=tools,
            messages=[
                {"role": "user", "content": "What's the weather in Tokyo?"},
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        }
                    ]
                }
            ]
        )

        print(follow_up.content[0].text)
```

---

## Summary

```mermaid
mindmap
  root((Tool Execution))
    Parse
      Extract function name
      Parse JSON arguments
      Get tool_call ID
    Execute
      Function registry
      Safe execution
      Error handling
    Return
      Format as tool message
      Include tool_call_id
      JSON serialize result
    Loop
      Check for more tool calls
      Continue until text response
```

---

## Quick Reference

```python
# Parse tool call
name = tool_call.function.name
args = json.loads(tool_call.function.arguments)

# Execute function
result = FUNCTIONS[name](**args)

# Return to LLM
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,
    "content": json.dumps(result)
})

# Get final response
response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tools
)
```

---

## What's Next?

You've mastered tool calling! Next month, we'll build **complete agents** that can reason, plan, and execute multiple tools autonomously!
