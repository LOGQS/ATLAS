# ag_builder_bot.py
import tkinter as tk
from tkinter import messagebox
import threading
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import re
import json
import os
from gui_element_manager import register_window, register_element, set_active_window, gui_manager

# Global chat history for chatboxes
chat_history_builder_bot = []
chat_history_current_agent = []

# Paths for JSON files
agent_file_path = r'agent_gen\agent_build\current.agent.json'
tools_file_path = r'agent_gen\agent_build\current_agent_tools.json'

def show_builder_bot_frame(main_app):
    main_app.build_frame.place_forget()

    builder_bot_frame = tk.Frame(main_app.main_frame, bg="#2c2c2c", bd=2, relief="ridge", padx=10, pady=10)
    builder_bot_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)

    register_window("builder_bot", builder_bot_frame)
    builder_bot_frame.bind("<FocusIn>", lambda e: set_active_window("builder_bot"))
    set_active_window("builder_bot")

    main_app.builder_bot_frame = builder_bot_frame

    close_button = tk.Button(
        builder_bot_frame,
        text="X",
        font=("Helvetica", 14, "bold"),
        bg="#ff5555",
        fg="white",
        command=lambda: close_builder_bot_frame(main_app)
    )
    close_button.place(x=902, y=5, width=25, height=25)
    register_element("builder_bot", "close_button", close_button, "button")

    # Chat frame 1
    chat_frame1 = tk.Frame(builder_bot_frame, bg="#2c2c2c")
    chat_frame1.place(x=150, y=70, width=375, height=520)
    register_element("builder_bot", "chat_frame1", chat_frame1, "frame")

    chatbox1 = tk.Text(chat_frame1, height=10, font=("Helvetica", 14), wrap="word", bg="#1a1a40", fg="white")
    chatbox1.pack(side="left", padx=10, pady=10, fill="both", expand=True)
    chatbox1.tag_configure("user", foreground="#d10404")
    chatbox1.tag_configure("agent", foreground="#02ad0a")
    main_app.chatbox1 = chatbox1
    register_element("builder_bot", "chatbox1", chatbox1, "text")

    scrollbar1 = tk.Scrollbar(chat_frame1, command=chatbox1.yview)
    scrollbar1.pack(side="right", fill="y")
    chatbox1.config(yscrollcommand=scrollbar1.set)

    # User input frame 1
    user_input_frame1 = tk.Frame(builder_bot_frame, bg="#2c2c2c")
    user_input_frame1.place(x=150, y=590, width=375, height=50)
    register_element("builder_bot", "user_input_frame1", user_input_frame1, "frame")

    user_input_box1 = tk.Entry(user_input_frame1, font=("Helvetica", 16), fg="black", bg="white")
    user_input_box1.pack(side="left", fill="x", expand=True, padx=10)
    user_input_box1.bind("<Return>", lambda event: send_message_to_builder_bot(main_app, 1))
    main_app.user_input_box1 = user_input_box1
    register_element("builder_bot", "user_input_box1", user_input_box1, "entry")

    send_button1 = tk.Button(user_input_frame1, text="Send", font=("Helvetica", 14), command=lambda: send_message_to_builder_bot(main_app, 1))
    send_button1.pack(side="right", padx=0)
    register_element("builder_bot", "send_button1", send_button1, "button")

    # Chat frame 2
    chat_frame2 = tk.Frame(builder_bot_frame, bg="#2c2c2c")
    chat_frame2.place(x=550, y=70, width=375, height=520)
    register_element("builder_bot", "chat_frame2", chat_frame2, "frame")

    chatbox2 = tk.Text(chat_frame2, height=10, font=("Helvetica", 14), wrap="word", bg="#1f1f4f", fg="white")
    chatbox2.pack(side="left", padx=10, pady=10, fill="both", expand=True)
    chatbox2.tag_configure("user", foreground="#d10404")
    chatbox2.tag_configure("agent", foreground="#02ad0a")
    main_app.chatbox2 = chatbox2
    register_element("builder_bot", "chatbox2", chatbox2, "text")

    scrollbar2 = tk.Scrollbar(chat_frame2, command=chatbox2.yview)
    scrollbar2.pack(side="right", fill="y")
    chatbox2.config(yscrollcommand=scrollbar2.set)

    # User input frame 2
    user_input_frame2 = tk.Frame(builder_bot_frame, bg="#2c2c2c")
    user_input_frame2.place(x=550, y=590, width=375, height=50)
    register_element("builder_bot", "user_input_frame2", user_input_frame2, "frame")

    user_input_box2 = tk.Entry(user_input_frame2, font=("Helvetica", 16), fg="black", bg="white")
    user_input_box2.pack(side="left", fill="x", expand=True, padx=10)
    user_input_box2.bind("<Return>", lambda event: send_message_to_current_agent(main_app))
    main_app.user_input_box2 = user_input_box2
    register_element("builder_bot", "user_input_box2", user_input_box2, "entry")

    send_button2 = tk.Button(user_input_frame2, text="Send", font=("Helvetica", 14), command=lambda: send_message_to_current_agent(main_app))
    send_button2.pack(side="right", padx=10)
    register_element("builder_bot", "send_button2", send_button2, "button")

    # Display boxes
    display_box1 = tk.Text(builder_bot_frame, height=5, width=20, font=("Helvetica", 14), wrap="word", bg="#03ad2e", fg="white")
    display_box1.place(x=20, y=30, width=120, height=30)
    main_app.display_box1 = display_box1
    register_element("builder_bot", "display_box1", display_box1, "text")

    display_box2 = tk.Text(builder_bot_frame, height=5, width=20, font=("Helvetica", 14), wrap="word", bg="#03ad2e", fg="white")
    display_box2.place(x=20, y=80, width=120, height=330)
    main_app.display_box2 = display_box2
    register_element("builder_bot", "display_box2", display_box2, "text")

    display_box3 = tk.Text(builder_bot_frame, height=5, width=20, font=("Helvetica", 14), wrap="word", bg="#03ad2e", fg="white")
    display_box3.place(x=20, y=450, width=120, height=120)
    main_app.display_box3 = display_box3
    register_element("builder_bot", "display_box3", display_box3, "text")

    # Save Agent button
    save_agent_button = tk.Button(
        builder_bot_frame,
        text="Save Current",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_agent(main_app)
    )
    save_agent_button.place(x=20, y=595, width=120, height=40)
    register_element("builder_bot", "save_agent_button", save_agent_button, "button")

    # Reset Chat buttons
    reset_button1 = tk.Button(
        builder_bot_frame,
        text="Reset Chat",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: reset_chat(main_app, 1)
    )
    reset_button1.place(x=300, y=30, width=120, height=40)
    register_element("builder_bot", "reset_button1", reset_button1, "button")

    reset_button2 = tk.Button(
        builder_bot_frame,
        text="Reset Chat",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: reset_chat(main_app, 2)
    )
    reset_button2.place(x=730, y=30, width=120, height=40)
    register_element("builder_bot", "reset_button2", reset_button2, "button")

    # Labels
    label1 = tk.Label(
        builder_bot_frame,
        text="Builder Bot",
        font=("Helvetica", 16),
        bg="#1a1a40",
        fg="white"
    )
    label1.place(x=160, y=30, width=120, height=40)
    register_element("builder_bot", "label1", label1, "label")

    label2 = tk.Label(
        builder_bot_frame,
        text="Current Agent",
        font=("Helvetica", 16),
        bg="#1f1f4f",
        fg="white"
    )
    label2.place(x=560, y=30, width=150, height=40)
    register_element("builder_bot", "label2", label2, "label")

def close_builder_bot_frame(main_app):
    main_app.builder_bot_frame.place_forget()
    main_app.build_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
    gui_manager.unregister_window("builder_bot")
    set_active_window("build_frame")

def send_message_to_builder_bot(main_app, chatbox_id):
    if chatbox_id == 1:
        user_message = main_app.user_input_box1.get()
        chatbox = main_app.chatbox1
    elif chatbox_id == 2:
        user_message = main_app.user_input_box2.get()
        chatbox = main_app.chatbox2
    else:
        return 

    if not user_message.strip():
        return 

    chatbox.insert(tk.END, f"You: {user_message}\n", "user")

    if chatbox_id == 1:
        main_app.user_input_box1.delete(0, tk.END)
        threading.Thread(target=send_message_to_model_builder_bot, args=(main_app, user_message, chatbox)).start()
    elif chatbox_id == 2:
        main_app.user_input_box2.delete(0, tk.END)

def send_message_to_model_builder_bot(main_app, user_message, chatbox):
    global chat_history_builder_bot

    try:
        response = call_gemini_model_builder_bot(main_app, user_message)
        process_model_response(main_app, response, chatbox)
        update_display_boxes(main_app)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

def call_gemini_model_builder_bot(main_app, user_request):
    global chat_history_builder_bot
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    generation_config = genai.types.GenerationConfig(
        response_mime_type = "application/json",
        temperature=1.0,
        max_output_tokens=8000,
    )

    system_prompt = r"""
    You are an intelligent, helpful agent builder. Your job is to build agents based on user requests. You get the necessary
    information from the user and develop using the information. When you get enough information, you start building the agent by
    filling the necessary variables using the " ANSWER FORMAT WHEN BUILDING THE AGENT:" section then you start building tool/s that
    the agent will use by filling the necessary variables using the "ANSWER FORMAT WHEN BUILDING THE TOOL/S:" section. 
    Use the following information while building the agent:
    
    IMPORTANT INFORMATION TO PAY ATTENTION TO WHILE BUILDING THE AGENT:
    - Agent name should be relevant to the agent's purpose.
    - Model should be selected based on the agent's purpose. Here are the available models and their advantages:
        - gemini-1.5-flash: Gemini 1.5 Flash is a fast and versatile multimodal model for scaling across diverse tasks.
            - Input: Text, Audio, Image, Video
            - Output: Text
            - Input token limit: 1.048.576
            - Output token limit: 8.192
            - Maximum number of images per prompt: 3600
            - Maximum video length: 1 hour
            - Maximum audio length: 9.5 hours
            - Maximum number of audio files: 1
        - gemini-1.5-pro: Gemini 1.5 Pro is a mid-size multimodal model that is optimized for a wide-range of reasoning tasks.
            - Input: Text, Audio, Image, Video
            - Output: Text
            - Input token limit: 1.048.576
            - Output token limit: 8.192
            - Maximum number of images per prompt: 3600
            - Maximum video length: 1 hour
            - Maximum audio length: 9.5 hours
            - Maximum number of audio files: 1
        - gemini-1.0-pro: Gemini 1.0 Pro is an NLP model that handles tasks like multi-turn text and code chat, and code generation.
            - Input: Text
            - Output: Text
            - Input token limit: 32.760
            - Output token limit: 8.192
    - Use gemini 1.5 pro when the task requires reasoning and understanding of complex information but does not require fast processing.
    - Use gemini 1.5 flash when the task requires fast processing and does require reasoning and understanding of complex information a little less.
    - Use gemini 1.0 pro when the task is really really simple and does not require multimodal input.
    - Update/create the agent/tools based on the user's request.
    - Only write the code for the tools in python. Do not write in any other language.
    - Your response should only include what is given in the "ANSWER FORMATS" section based on the stage you are in.
    - Agent/Tool build will be done in the background while the "User Display" section will be shown to the user.
    - Only use user_display until the agent is ready to be built. After that, ask the user for confirmation to build the agent.
    - ONLY BUILD THE AGENT WHEN THE USER CONFIRMS TO DO SO. NEVER BUILD THE AGENT WITHOUT USER'S CONFIRMATION.
    - After you build the agent, ask the user if they need any updates or changes to the agent. If they do, rewrite the agent accordingly
    then provide the updated agent to the user. After that ask the user if the agent build is satisfactory. Then move on to building the tools.
    - ONLY START BUILD THE TOOL/S WHEN THE USER CONFIRMS TO DO SO. NEVER START BUILDING THE TOOL/S WITHOUT USER'S CONFIRMATION.
    - Even when you are building the agent/tool/s, keep the user_display section updated with explaning what you did to inform the user. You should
    always write something in the user_display section.
    - In the answer format, you can only change the parts delimited by square brackets. Do not change anything else.
    - Always provide a extractor tool if the agent needs to use a tool. The agent can't use a tool without an extractor tool. It can only provide a textual
    response so an extractor tool is necessary to extract the part necessary from the model's response to execute the tool usage.
    - Always prompt the model so that the extractor tool can extract the necessary information from the model's response without any errors.
    - DO NOT leave any room for ambiguity in the prompt. The prompt should be clear and concise. And it should always have a answer format
    section to guide the agent on how to respond.
    - Your chat with the user should include 3 stages. The first stage is the information gathering stage. In this stage you gather information from the user
    to understand, how you should build the agent and the tool/s. In this stage after you gather enough information, you move onto the MOST IMPORTANT PART. IN THIS
    PART YOU NEED TO PAY A LOT OF ATTENTION. BE INTELLIGENT, CREATIVE AND THINK STEP BY STEP. Based on the iformation you've gathered, you provide a highly detailed, 
    structured overview and flow of the fully working agent. You specify how the agent will work, how it will be able to use the tools, how the tools will work, how the
    task will be achieved at the end of this process, how the prompting of the agent will be etc. You need to define everything textually without any code. You imagine 
    a workflow and simulate an example to make sure that the agent will work. Imagine how the user will write to the agent, how the agent will respond, how this response
    will get extracted, how the tool will get executed with this extracted information, how the agent will get the extracted information and see it in the prompt, then how
    the agent will give the final response. Don't forget, you prompt the agent once, even though it has chat history, you need to prompt the agent so that it understands
    when to provide in a format to answer the user and when the provide in a format the use the tool. You need to define the variables in the prompt so that the model can
    see it and use it. Think down to last detail, be logical and professional. You end this stage when you have enough information to build the agent and when you get user
    confirmation. The second stage is the agent building stage. In this stage, you give the agent a name, choose the model, prompt it, choose if it needs tools,
    if it needs tools, you choose which tools it needs + give it the extractor tool(This tool should always be called extractor tool), then lastly you choose the
    advanced settings. You end this stage when the built agent is satisfactory to the user and when you get user confirmation. The last stage is the tool building
    stage. In this stage, you build the tools that the agent will use. If the agent doesn't need any tools, you skip this stage. If the agent needs tools, you build
    the necessary tools one by one, then you build the extractor tool. You end this stage when the built tools are satisfactory to the user and when you get user
    confirmation. After you finish all 3 stages, you tell the user that the agent is ready to use and you provide the user with the agent's name and the tools that
    the agent will use. You also provide the user with the necessary information on how to use the agent and the tools. Then you ask the user if they need anything
    else. If they do, you start the process again from the first stage.
    - "ANSWER FORMAT" section includes both the agent and the tool/s for teaching purposes. But normally you would only provide the necessary part based on the
    current stage of the chat. This means always providing the user_display section, providing the agent part in building the agent stage, and providing the tool/s
    part in building the tool/s stage. You should never provide the agent part in the tool/s building stage and vice versa.
    - First understand what stage you are in, then provide the necessary part based on the current stage.
    - If you are currently building the agent, provide your response using the "ANSWER FORMAT WHEN BUILDING THE AGENT" section. DO not write anything else in your response.
    - If you are currently building the tool/s, provide your response using the "ANSWER FORMAT WHEN BUILDING THE TOOL/S" section. Do not write anything else in your response.
    - Before you start building the agent, think of the tools the agent needs to use. The agent is basically a prompted LLM model without the tools. So it can already do
    everything that an LLM model can do. But if it is not something that an LLM model can do, then you need to build the necessary tools for the agent to use. And if you need
    tool/s, you should always include and build the extractor tool. The extractor tool is the tool that extracts the necessary information from the model's response so that the
    main tool/s can use the extracted information directly.
    - An LLM model can already summarize, translate, answer questions, generate code, generate text, etc. So you don't need to build a tool for these tasks.
    - NEVER CREATE A TOOL THAT THE AGENT DOESN'T NEED. NO TOOL SHOULD INCLUDE THE FOLLOWING FUNCTIONALITIES. THESE SHOULD BE DONE BY THE LLM MODEL ALONE.
      THIS INCLUDES TOOLS AND TOOLS SIMILAR TO THE FOLLOWING:
      Any type of Summarization Tool, Translation Tool, Question Answering Tool, Language Processing Tool such as formatting etc., Code Generation Tool, Text Generation Tool, etc.
    - When the agent needs to do something that an LLM model can do alone such as summarization, translation, question answering, code generation, text generation, language
     processing etc.
    you can just prompt the model and the model will do the task. 
    - When the agent needs to do something that an LLM model can't do alone such as searching a file in the system, then something that an LLM model can do alone such as 
    summarizing the file, then this would require for the model to use the tool, get the output from the tool then summarize the output. In this case, you would build a tool 
    that searches the file in the system then extracts the text from the file, then you would define a variable that holds this extracted text, then write this variable in the
    "Tool Variable/s To The Model" section of the tool. When there was something in the variable, the model would be able to see it and use it. You would prompt the model so that
    when the part of the prompt that holds the variable is empty, the model would know that it should use the tool to get the necessary information. Then when the part gets filled
    with the extracted information, you would prompt the model so that the model would know that it should summarize the extracted information. Then it would provide the summary.
    So you need to define the variables both in the prompt and if necessary in the tool/s. The variables should be defined in the prompt so that the model can see it and use it.
    The variables should be defined in the tool/s so that the tool/s can provide the necessary information to the model.
    - Provide the variable in the prompt as {variable} and in the tool/s as variable. The variable should be the same in both the prompt and the tool/s. Use the previous techniques
    I mentioned while using the variable in the prompt and the tool/s.
    - Tools are basically code blocks/scripts that the agent will use to perform a task that an LLM model can't do alone.
    - If you are building a tool, you should always build the extractor tool too.
    - PROVIDE THE CORRESPONDING PARTS ALWAYS IN JSON FORMAT. THIS MEANS OTHER THAN THE USER DISPLAY PART, ALL PARTS SHOULD BE IN JSON FORMAT.
    - While designing the agent, you should think of how it will work then prompt and adjust the agent accordingly. The relationship between the agent prompt, the extractor tool
    and the tools is crucial for the agent to work properly. The agent prompt should be clear and concise so that the extractor tool can extract the necessary information from the
    model's response without any errors. Then the extractor tool should be able to format the extracted information so that the main tool/s can use the extracted information directly.
    Here is a case of how the agent prompt, the extractor tool and the main tool should work together to satisfy the purpose of the agent:
    What I am trying to do: I am trying to make an agent that multiplies the number given by the user by 2. 
    Agent Prompt: "You are a number extractor agent. The user will provide you with a number and you will extract the number from the user's input. Then you will 
    provide the extracted number to the user. Your responses should always and only include the extracted number like given in the following format:
    Extracted_Number: [Extracted number from the user's input]
    Then now that we extracted the number from the user request using the prompted agent, we should build the extractor tool that will extract the number from the agent's response.
    Then we will build the tool that will multiply the extracted number by 2 then print the result to the user.
    Extractor Tool Code would be: 
    import re

    def extract_number(text):
        pattern = r'Extracted_Number:\s*\[(\d+\.?\d*)\]'
        match = re.search(pattern, text)
        if match:
            number_str = match.group(1)
            if '.' in number_str:
                return float(number_str)
            else:
                return int(number_str)
        else:
            return None
    The tool that will multiply the extracted number by 2 would be:

    def multiply_by_two(number):
        print(number * 2)

    This is how the agent prompt, the extractor tool and the main tool should work together to satisfy the purpose of the agent. The agent prompt should always be clear and concise
    so that the extractor tool can extract the necessary information from the model's response without any errors. The extractor tool should be able to format the extracted 
    information so that the main tool/s can use the extracted information directly. Don't forget this is just a simple example. You should be smart and creative while designing the agent.

    --------------------------------------------

    ANSWER FORMATS:  

    ANSWER FORMAT WHEN BUILDING THE AGENT:
 
    User_display:[Write here the response that you want to display to the user.]

    {
        "Agent Name": "[Name of the agent]",
        "Model": "[gemini-1.5-flash or gemini-1.5-pro or gemini-1.0-pro]",
        "Agent Prompt": "[Prompt for the agent]",
        "Tools": [
            "Extractor Tool",
            "[Tool 1 Name]",
            "[Tool 2 Name]",
            ...
        ],
        "Advanced Settings": {
            "Top p": "[Default: 1.0 (float between 0.0 and 1.0)]",
            "Top k": "[Default: 50 (integer between 1 and 100)]",
            "Temperature": "[Default: 1.0 (float between 0.0 and 1.0)]",
            "Max output length": "[Default: 1000 (integer between 1 and 8192)]"
        }
    }

    ANSWER FORMAT WHEN BUILDING THE TOOL/S:

    User_display:[Write here the response that you want to display to the user.]

    {
        "Tool1 Name": "Extractor Tool"
        "Tool1 Description": "[Short description of the tool]",
        "Tool1 Code": "[Full code of the tool]"
    }
    {
        "Tool2 Name": "[Name of the tool]",
        "Tool2 Description": "[Short description of the tool]",
        "Tool2 Code": "[Full code of the tool]"
    }
    {
        "Tool3 Name": "[Name of the tool]",
        "Tool3 Description": "[Short description of the tool]",
        "Tool3 Code": "[Full code of the tool]"
    }
    ...
    """
    model = genai.GenerativeModel(model_name="gemini-1.5-pro", system_instruction=system_prompt)
    chat = model.start_chat(history=chat_history_builder_bot)
    prompt = f"User: {user_request}"

    chat_response = chat.send_message(content=prompt, generation_config=generation_config, safety_settings=safety_settings)
    chat_history_builder_bot = chat.history
    print(chat_response.text)

    return chat_response.text

def send_message_to_current_agent(main_app):
    user_message = main_app.user_input_box2.get()
    chatbox = main_app.chatbox2

    if not user_message.strip():
        return

    chatbox.insert(tk.END, f"You: {user_message}\n", "user")
    main_app.user_input_box2.delete(0, tk.END)
    threading.Thread(target=send_message_to_model_current_agent, args=(main_app, user_message, chatbox)).start()

def send_message_to_model_current_agent(main_app, user_message, chatbox):
    global chat_history_current_agent

    try:
        response = call_gemini_model_current_agent(main_app, user_message)
        chatbox.insert(tk.END, f"Agent: {response}\n", "agent")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

def call_gemini_model_current_agent(main_app, user_request):
    global chat_history_current_agent
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])

    agent_file_path = r'agent_gen\agent_build\current_agent.json'
    
    if not os.path.exists(agent_file_path):
        raise FileNotFoundError("No current agent found. Please create an agent first.")

    with open(agent_file_path, 'r') as f:
        agent_data = json.load(f)

    try:
        model_name = agent_data["Model"]
        system_prompt = agent_data["Agent Prompt"]
        advanced_settings = agent_data["Advanced Settings"]

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        generation_config = genai.types.GenerationConfig(
            temperature=float(advanced_settings["Temperature"]),
            max_output_tokens=int(advanced_settings["Max output length"]),
            top_p=float(advanced_settings["Top p"]),
            top_k=int(advanced_settings["Top k"]),
        )

        model = genai.GenerativeModel(model_name=model_name)
        chat = model.start_chat(history=chat_history_current_agent)
        prompt = f"System: {system_prompt}\nUser: {user_request}"

        chat_response = chat.send_message(content=prompt, generation_config=generation_config, safety_settings=safety_settings)
        chat_history_current_agent = chat.history

        return chat_response.text

    except KeyError as e:
        raise KeyError(f"Missing key in agent data: {e}")


def sanitize_json(json_string):
    print(f"Original JSON string: {json_string}")
    
    # Remove triple backticks around JSON for easier processing
    json_string = re.sub(r'```json|```', '', json_string)
    print(f"JSON string after removing triple backticks: {json_string}")

    # Remove control characters
    control_char_pattern = r'[\x00-\x1F\x7F]'
    json_string = re.sub(control_char_pattern, '', json_string)
    print(f"JSON string after removing control characters: {json_string}")

    # Ensure the JSON ends with a closing bracket
    if not json_string.endswith('}'):
        json_string += '}'
    print(f"JSON string after ensuring closing bracket: {json_string}")

    # Decode the JSON without the problematic sections
    try:
        json_data = json.loads(json_string)
        print(f"Successfully decoded JSON data: {json_data}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON part: {e}\nContent: {json_string}")
        return None

    return json_data

def process_model_response(main_app, response, chatbox):
    try:
        response = response.strip()
        print(f"Original response: {response}")
        
        # Remove triple backticks around JSON for easier processing
        response_cleaned = re.sub(r'```json|```', '', response)
        print(f"Response after removing triple backticks: {response_cleaned}")

        # Identify and handle different response types
        if "User_display:" in response_cleaned:
            # Type 1: Only user display
            if "{" not in response_cleaned:
                user_display_content = response_cleaned.split("User_display:")[1].strip()
                chatbox.insert(tk.END, f"Agent: {user_display_content}\n", "agent")
                print(f"User display content: {user_display_content}")
                json_blocks = []
            else:
                # Type 2 and 3: User display with JSON
                user_display_content = re.search(r'User_display:(.*?)(?=\{)', response_cleaned, re.DOTALL).group(1).strip()
                chatbox.insert(tk.END, f"Agent: {user_display_content}\n", "agent")
                print(f"User display content: {user_display_content}")
                json_blocks = re.findall(r'(\{.*\})', response_cleaned, re.DOTALL)
                print(f"JSON blocks found: {json_blocks}")
        else:
            # Fallback: Assume response is JSON or special case without User_display
            json_blocks = re.findall(r'(\{.*\})', response_cleaned, re.DOTALL)
            print(f"JSON blocks found: {json_blocks}")
            user_display_content = response_cleaned if not json_blocks else ""
            if user_display_content:
                chatbox.insert(tk.END, f"Agent: {user_display_content}\n", "agent")
                print(f"User display content: {user_display_content}")

        # Process each JSON block
        for json_block in json_blocks:
            print(f"Processing JSON block: {json_block}")
            try:
                # Clean and sanitize JSON block
                json_block_cleaned = sanitize_json(json_block.strip())
                
                if json_block_cleaned is None:
                    continue
                
                # Save agent data
                if "Agent Name" in json_block_cleaned:
                    save_agent_data(json_block_cleaned)
                    print(f"Saved agent data: {json_block_cleaned}")
                # Save tools data
                elif any(f"Tool{i} Name" in json_block_cleaned for i in range(1, 10)):
                    save_tools_data([json_block_cleaned])
                    print(f"Saved tools data: {json_block_cleaned}")
                else:
                    # Handle multiple tools
                    tools = [json_block_cleaned]
                    for i in range(2, 10):  
                        tool_key = f"Tool{i} Name"
                        if tool_key in json_block_cleaned:
                            tools.append(json_block_cleaned)
                    save_tools_data(tools)
                    print(f"Saved tools data: {tools}")
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON part: {e}\nContent: {json_block}")

    except Exception as e:
        print(f"Error processing response: {e}")

    update_display_boxes(main_app)

def save_agent_data(agent_data):
    try:
        agent_file_path = r'agent_gen\agent_build\current_agent.json'
        os.makedirs(os.path.dirname(agent_file_path), exist_ok=True)
        with open(agent_file_path, 'w', encoding='utf-8') as f:
            json.dump(agent_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving agent data: {e}")

def save_tools_data(tools_data):
    try:
        tools_file_path = r'agent_gen\agent_build\current_agent_tools.json'
        existing_tools = []

        # Read existing tools if the file exists
        if os.path.exists(tools_file_path):
            with open(tools_file_path, 'r', encoding='utf-8') as f:
                existing_tools = json.load(f)

        # Process each new tool
        for new_tool in tools_data:
            new_tool_number = new_tool.get('Tool1 Name', '').split(' ')[0]
            replaced = False

            # Check if the new tool number matches any existing tool number
            for i, existing_tool in enumerate(existing_tools):
                existing_tool_number = existing_tool.get('Tool1 Name', '').split(' ')[0]
                if existing_tool_number == new_tool_number:
                    existing_tools[i] = new_tool 
                    replaced = True
                    break

            if not replaced:
                existing_tools.append(new_tool)

        with open(tools_file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_tools, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving tools data: {e}")

def update_display_boxes(main_app):
    try:
        agent_file_path = r'agent_gen\agent_build\current_agent.json'
        tools_file_path = r'agent_gen\agent_build\current_agent_tools.json'

        agent_name, agent_prompt, tools_names = 'No agent name available', 'No prompt available', 'No tools available'

        if os.path.exists(agent_file_path):
            with open(agent_file_path, 'r', encoding='utf-8') as f:
                agent_data = json.load(f)
            agent_name = agent_data.get('Agent Name', agent_name)
            agent_prompt = agent_data.get('Agent Prompt', agent_prompt)

        if os.path.exists(tools_file_path):
            with open(tools_file_path, 'r', encoding='utf-8') as f:
                tools_data = json.load(f)
            tools_names = "\n".join([tool.get('Tool1 Name', 'No tool name available') for tool in tools_data])

        main_app.display_box1.delete("1.0", tk.END)
        main_app.display_box1.insert(tk.END, f"Agent Name: {agent_name}\n")
        adjust_text_size(main_app.display_box1)

        main_app.display_box2.delete("1.0", tk.END)
        main_app.display_box2.insert(tk.END, f"Prompt: {agent_prompt}\n")
        adjust_text_size(main_app.display_box2)

        main_app.display_box3.delete("1.0", tk.END)
        main_app.display_box3.insert(tk.END, f"Tools: {tools_names}\n")
        adjust_text_size(main_app.display_box3)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while updating displays: {e}")

def adjust_text_size(text_widget):
    content = text_widget.get("1.0", tk.END)
    max_length = max(len(line) for line in content.split("\n"))
    if max_length <= 30:
        text_widget.config(font=("Helvetica", 16))
    elif max_length <= 60:
        text_widget.config(font=("Helvetica", 14))
    else:
        text_widget.config(font=("Helvetica", 12))


def save_agent(main_app):
    agent_file_path = r'agent_gen\agent_build\current_agent.json'
    tools_file_path = r'agent_gen\agent_build\current_agent_tools.json'
    saved_agents_path = r'agent_gen\saved_agents\agents.json'
    saved_tools_path = r'agent_gen\saved_tools\tools.json'

    if not os.path.exists(agent_file_path) and not os.path.exists(tools_file_path):
        messagebox.showerror("Error", "No agent or tools are currently being worked on. Please create an agent or tool first.")
        return

    if os.path.exists(agent_file_path):
        with open(agent_file_path, 'r') as f:
            current_agent = json.load(f)

        if os.path.exists(saved_agents_path):
            with open(saved_agents_path, 'r') as f:
                saved_agents = json.load(f)
        else:
            saved_agents = []

        saved_agents.append(current_agent)

        with open(saved_agents_path, 'w') as f:
            json.dump(saved_agents, f, indent=4)

        os.remove(agent_file_path)

    if os.path.exists(tools_file_path):
        with open(tools_file_path, 'r') as f:
            current_tools = json.load(f)

        if os.path.exists(saved_tools_path):
            with open(saved_tools_path, 'r') as f:
                saved_tools = json.load(f)
        else:
            saved_tools = []


        for tool in current_tools:
            processed_tool = {}
            for i in range(1, 10):
                if f"Tool{i} Name" in tool:
                    processed_tool["Tool Name"] = tool[f"Tool{i} Name"]
                    processed_tool["Tool Description"] = tool.get(f"Tool{i} Description", "")
                    processed_tool["Tool Code"] = tool.get(f"Tool{i} Code", "")
                    break 
            if processed_tool:
                saved_tools.append(processed_tool)

        with open(saved_tools_path, 'w') as f:
            json.dump(saved_tools, f, indent=4)

        os.remove(tools_file_path)

    messagebox.showinfo("Success", "Agent and/or tools saved successfully. Current data cleared.")

def reset_chat(main_app, chatbox_id):
    global chat_history_builder_bot, chat_history_current_agent
    if chatbox_id == 1:
        main_app.chatbox1.delete('1.0', tk.END)
        chat_history_builder_bot = []
    elif chatbox_id == 2:
        main_app.chatbox2.delete('1.0', tk.END)
        chat_history_current_agent = []