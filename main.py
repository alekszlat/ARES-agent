import requests
import os

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8080/completion")

SYSTEM_PROMPT = """ You are a helpful assistant
<|start_header_id|>system<|end_header_id|>

You are an expert in composing functions. You are given a question and a set of possible functions. 
Based on the question, you will need to make one or more function/tool calls to achieve the purpose. 
If none of the functions can be used, point it out. If the given question lacks the parameters required by the function,also point it out. You should only return the function call in tools call sections.
If you decide to invoke any of the function(s), you MUST put it in the format of [func_name1(params_name1=params_value1, params_name2=params_value2...), func_name2(params)]
You SHOULD NOT include any other text in the response.

Here is a list of functions in JSON format that you can invoke.
[
    {
        "name": "get_user_name",
        "description": "Retrieve a name for a specific user by their unique identifier. Note that the provided function is in Python 3 syntax.",
        "parameters": {
            "type": "dict",
            "required": [
                "user_id"
            ],
            "properties": {
                "user_id": {
                 "type": "integer",
                 "description": "The unique identifier of the user. It is used to fetch the specific user details from the database."
             }
            }
        }
    }
]
<|eot_id|>"""

def request(prompt: str, n_predict: int = 64) -> str:
    prompt_set = f"""{SYSTEM_PROMPT}\n
    <|start_header_id|>user<|end_header_id|>
    \n{prompt}\n
    <|eot_id|>
    <|start_header_id|>assistant<|end_header_id|>"""

    response = requests.post(
        LLM_ENDPOINT,
        json={
            "prompt": prompt_set,
            "n_predict": n_predict,
            "temperature": 0,
            "top_p": 0.7,
            "stop": ["<|eot_id|>"],
        },
    )

    return response.json().get("content", "")


def main():
    question = "Can you retrieve the name of the user with the ID 7890?"
    response = request(question, n_predict=256)
    print("Response from LLM:")
    print(response)


if __name__ == "__main__":
    main()
