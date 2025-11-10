import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from prompts import MASTER_PROMPT

store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    """
    Fetches the chat history for a given session_id.
    If no history exists, a new one is created.
    """
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def parse_response(raw_output: str) -> str:
    match = re.search(f"<response>(.*)</response>", raw_output, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        print("\n[Debug: Parser failed to find <response> tags. Returning raw output.]")
        return raw_output

def main():
    load_dotenv()
    if os.getenv("OPENAI_API_KEY") is None:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    
    llm = ChatOpenAI(model="gpt-4", temperature=0)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", MASTER_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{user_input}")
    ])

    # send the user input -> prompt, then send to LLM
    chain = prompt_template | llm

    chain_with_memory = RunnableWithMessageHistory(
        chain,
        get_session_history, # f(session_id)->history
        input_messages_key="user_input",
        history_messages_key="chat_history",
    )

    print("Elenchus Agent is online. Type 'exit' to quit.")

    session_id = "enlechus_session"
    while True:
        try:
            user_input = input("\nYou: ")

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting Elenchus Agent. Goodbye!")
                break

            print("\nTutor: (Thinking...)")
            config = {"configurable": {"session_id": session_id}}
            # .invoke() runs the chain once + get full response
            raw_response = chain_with_memory.invoke({"user_input": user_input}, config=config)

            raw_content = raw_response.content

            clean_response = parse_response(raw_content)

            print(f"\rTutor: {clean_response}\n")

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nExiting Elenchus Agent. Goodbye!")
            break

if __name__ == "__main__":
    main()
