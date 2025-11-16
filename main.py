import os
import re
import json
import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage
from prompts import MASTER_PROMPT, SOLVER_PROMPT

SHOW_RAW_OUTPUT = True

store = {} #"session_id" -> {"history": ChatMessageHistory, "solution": str}

def get_session(session_id: str) -> dict:
    """
    Fetches the full session data (history and solution) for a given session_id.
    If no session exists, a new one is created.
    """
    if session_id not in store:
        store[session_id] = {
            "history": ChatMessageHistory(),
            "solution": None,
        }
    return store[session_id]

def get_session_history(session_id: str) -> ChatMessageHistory:
    """
    Fetches only the chat history for a given session_id.
    This is the function requiured by RunnableWithMessageHistory.
    """
    return get_session(session_id)["history"]

def save_session_to_json(session_id: str):
    """
    Saves the complete session (solution + history) to a timestamped JSON file.
    """
    if session_id not in store:
        print("\n[Traceability: No session data to save.]")
        return

    print("\n[Traceability: Saving session log...]")
    session_data = get_session(session_id)
    history = session_data["history"]
    solution = session_data["solution"]

    # Prepare the data for JSON output
    output_data = {
        "session_id": session_id,
        "generated_solution": solution,
        "conversation": []
    }

    for msg in history.messages:
        if isinstance(msg, HumanMessage):
            output_data["conversation"].append({
                "role": "human",
                "content": msg.content
            })
        elif isinstance(msg, AIMessage):
            raw_content = msg.content
            parsed_response = parse_response(raw_content) if not SHOW_RAW_OUTPUT else raw_content
            
            output_data["conversation"].append({
                "role": "ai",
                "parsed_response": parsed_response,
                "raw_output": raw_content
            })

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_log_{session_id}_{timestamp}.json"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4)
        print(f"[Traceability: Session saved successfully to {filename}]")
    except Exception as e:
        print(f"[Traceability: Error saving session - {e}]")

def parse_response(raw_output: str) -> str:
    """
    Parses the raw output from the LLM to extract the content within <response>...</response> tags.
    If the tags are not found, returns the raw output.
    """
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
    solver_prompt = ChatPromptTemplate.from_messages([("system", SOLVER_PROMPT), ("human", "{user_input}")])
    solver_chain = solver_prompt | solver_llm | StrOutputParser()
    
    coach_llm = ChatOpenAI(model="gpt-4o", temperature=0)
    coach_prompt_template = ChatPromptTemplate.from_messages([
        ("system", MASTER_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("system", "Here is the expert solution for your reference: {solution}"),
        ("human", "{user_input}")
    ])

    # send the user input -> prompt, then send to LLM
    coach_base_chain = coach_prompt_template | coach_llm

    def get_or_generate_solution(input_dict: dict, config: RunnableConfig):
        """
        This function returns the solution string.
        """
        session_id = config["configurable"]["session_id"]
        session_data = get_session(session_id)

        if session_data["solution"]:
            print("\nTutor: (Using cached solution...)")
            return session_data["solution"]
        else:
            print("\nTutor: (Consulting expert...)")
            solution = solver_chain.invoke({"user_input": input_dict["user_input"]}, config)
            session_data["solution"] = solution
            return solution
            
    orchestrator_chain = RunnablePassthrough.assign(
        solution=RunnableLambda(get_or_generate_solution)
    ) | coach_base_chain

    chain_with_memory = RunnableWithMessageHistory(
        orchestrator_chain,
        get_session_history, # f(session_id)->history
        input_messages_key="user_input",
        history_messages_key="chat_history",
    )

    def start_new_session(session_id: str, is_reset: bool = False):
        """
        Initialises a new session.
        """
        if is_reset:
            print("\n...Clearing session memory...")

        store.pop(session_id, None)

        session_data = get_session(session_id)

        intro_message = "Hello, I'm Elenchus. What problem can I help you with today?"

        session_data["history"].add_ai_message(intro_message)

        if is_reset:
            print("Session cleared. Please ask a new problem.")

        print(f"\nTutor: {intro_message}\n")

    print("Elenchus Agent v2.0 (Multi-Agent) is online.")
    print("Type 'exit' to quit, type 'clear' to reset and start a new problem.")

    session_id = "enlechus_user_v2_stateful"

    start_new_session(session_id, is_reset=False)

    while True:
        try:
            user_input = input("\nYou: ")

            if user_input.lower() in ["exit", "quit"]:
                save_session_to_json(session_id)
                print("Exiting Elenchus Agent. Goodbye!")
                break

            if user_input.lower() in ["clear", "reset"]:
                start_new_session(session_id, is_reset=True)
                continue

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
            print("\n[Traceability: Interrupted. Saving session...]")
            save_session_to_json(session_id)
            print("\nExiting Elenchus Agent. Goodbye!")
            break

if __name__ == "__main__":
    main()
