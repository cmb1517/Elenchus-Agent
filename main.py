import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory
from prompts import MASTER_PROMPT, SOLVER_PROMPT

SHOW_RAW_OUTPUT = True

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
    
    solver_llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    solver_prompt = ChatPromptTemplate.from_messages([("human", SOLVER_PROMPT), ("human", "{user_input}")])
    solver_chain = solver_prompt | solver_llm | StrOutputParser()
    
    coach_llm = ChatOpenAI(model="gpt-4", temperature=0)
    coach_prompt_template = ChatPromptTemplate.from_messages([
        ("system", MASTER_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "Here is my message: {user_input}\n\nHere is the expert solution for your reference: {solution}")
    ])

    # send the user input -> prompt, then send to LLM
    coach_base_chain = coach_prompt_template | coach_llm

    # user_input -> solver_chain -> solution
    # then user_input + solution -> coach_base_chain
    orchestrator_chain = RunnablePassthrough().assign(
        solution=solver_chain
    ) | coach_base_chain

    chain_with_memory = RunnableWithMessageHistory(
        orchestrator_chain,
        get_session_history, # f(session_id)->history
        input_messages_key="user_input",
        history_messages_key="chat_history",
        # Note: We only add the *user_input* and *coach's response* to history.
        # The "solution" is re-generated every time, which is fine for now.
    )

    print("Elenchus Agent v2.0 (Multi-Agent) is online. (Type 'exit' to quit).")

    session_id = "enlechus_user_v2"
    while True:
        try:
            user_input = input("\nYou: ")

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting Elenchus Agent. Goodbye!")
                break

            print("\nTutor: (Consulting expert...)")
            config = {"configurable": {"session_id": session_id}}
            # .invoke() runs the chain once + get full response
            raw_response = chain_with_memory.invoke({"user_input": user_input}, config=config)

            raw_content = raw_response.content
            if SHOW_RAW_OUTPUT:
                final_response = raw_content
            else:
                final_response = parse_response(raw_content)

            print(f"\rTutor: {final_response}\n")

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nExiting Elenchus Agent. Goodbye!")
            break

if __name__ == "__main__":
    main()
