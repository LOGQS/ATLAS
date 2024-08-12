# ag_canvas_workflow.py
import subprocess
import json
import os
import re
import sys

WORKFLOW_DIR = r'agent_gen\saved_workflows'
WORKFLOW_PY_PATH = os.path.join(WORKFLOW_DIR, 'workflow.py')

def generate_workflow_code(workflow_data):
    try:
        with open('config/config.json', 'r') as config_file:
            config = json.load(config_file)
            api_key = config['api_keys']['GEMINI_API_KEY']
    except Exception as e:
        print(f"Error loading API key from config file: {e}")
        api_key = "YOUR_API_KEY_HERE" 

    code_lines = [
        "# workflow.py",
        "import sys",
        "import io",
        "import random",
        "import threading",
        "import queue",
        "import inspect",
        "import google.generativeai as genai",
        "from google.generativeai.types import HarmCategory, HarmBlockThreshold",
        "import tkinter as tk",
        "from tkinter import scrolledtext",
        "",
        f"GEMINI_API_KEY = '{api_key}'",
        "genai.configure(api_key=GEMINI_API_KEY)",
        "",
        "def colored_print(text, name):",
        "    try:",
        "        print(f'{name}: {text}')",
        "    except UnicodeEncodeError:",
        "        fallback_text = text.encode('ascii', 'ignore').decode('ascii')",
        "        print(f'{name}: {fallback_text} (Unicode characters removed)')",
        "",
        "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')",
        "",
        "class WorkflowApp(tk.Tk):",
        "    def __init__(self):",
        "        super().__init__()",
        "        self.title('Workflow Execution')",
        "        self.geometry('800x600')",
        "        self.configure(bg='#1e1e1e')",
        "        self.create_widgets()",
        "        self.colors = {}",
        "        self.results = {}",
        "        self.tools = {}",
        "        self.execution_queue = queue.Queue()",
        "        self.result_queue = queue.Queue()",
        "        self.setup_tools()",
        "",
        "    def create_widgets(self):",
        "        self.chat_frame = tk.Frame(self, bg='#2c2c2c')",
        "        self.chat_frame.pack(padx=10, pady=10, fill='both', expand=True)",
        "        self.chatbox = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, bg='#1f1f3b', fg='white', font=('Helvetica', 12))",
        "        self.chatbox.pack(padx=10, pady=10, fill='both', expand=True)",
        "        self.input_frame = tk.Frame(self.chat_frame, bg='#2c2c2c')",
        "        self.input_frame.pack(padx=10, pady=(0, 10), fill='x')",
        "        self.user_input = tk.Entry(self.input_frame, font=('Helvetica', 12))",
        "        self.user_input.pack(side='left', fill='x', expand=True)",
        "        self.user_input.bind('<Return>', self.send_message)",
        "        self.send_button = tk.Button(self.input_frame, text='Send', command=self.send_message)",
        "        self.send_button.pack(side='right', padx=(10, 0))",
        "",
        "    def send_message(self, event=None):",
        "        user_message = self.user_input.get()",
        "        if user_message:",
        "            self.chatbox.insert(tk.END, f'You: {user_message}\\n')",
        "            self.user_input.delete(0, tk.END)",
        "            threading.Thread(target=self.process_workflow, args=(user_message,)).start()",
        "",
        "    def colored_insert(self, text, name):",
        "        if name not in self.colors:",
        "            self.colors[name] = f'#{random.randint(0, 0xFFFFFF):06x}'",
        "        self.chatbox.insert(tk.END, f'[{name}]: ', self.colors[name])",
        "        self.chatbox.insert(tk.END, f'{text}\\n')",
        "        self.chatbox.see(tk.END)",
        "        self.update()",
        "",
        "    def process_workflow(self, user_message):",
        "        self.results.clear()",
        "        execution_order = self.topological_sort()",
        "        first_node = self.get_node_by_id(execution_order[0])",
        "        if first_node['type'] == 'tool':",
        "            input_data = self.parse_tool_input(first_node['name'], user_message)",
        "        else:",
        "            input_data = {'user_message': user_message}",
        "        self.execution_queue.put((execution_order[0], input_data))",
        "",
        "        # Set to keep track of processed nodes",
        "        processed_nodes = set()",
        "",
        "        threads = []",
        "        for _ in range(min(len(execution_order), 5)):",
        "            t = threading.Thread(target=self.worker, args=(processed_nodes,))",
        "            t.start()",
        "            threads.append(t)",
        "",
        "        for node_id in execution_order[1:]:",
        "            self.execution_queue.put((node_id, None))",
        "",
        "        for t in threads:",
        "            t.join()",
        "",
        "        while not self.result_queue.empty():",
        "            node_id, result = self.result_queue.get()",
        "            self.results[node_id] = result",
        "            node = self.get_node_by_id(node_id)",
        "            self.colored_insert(str(result), node['name'])",
        "            colored_print(str(result), node['name'])",
        "",
        "    def worker(self, processed_nodes):",
        "        while True:",
        "            try:",
        "                node_id, input_data = self.execution_queue.get(timeout=1)",
        "                if node_id in processed_nodes:",
        "                    self.execution_queue.task_done()",
        "                    continue",
        "",
        "                node = self.get_node_by_id(node_id)",
        "                if input_data is None:",
        "                    input_data = self.get_node_inputs(node_id, self.results)",
        "                if not self.check_inputs_ready(node_id, input_data):",
        "                    self.execution_queue.put((node_id, None))",
        "                    self.execution_queue.task_done()",
        "                    continue",
        "                if node['type'] == 'tool':",
        "                    result = self.process_tool(node, input_data)",
        "                else:",
        "                    result = self.process_agent(node, input_data)",
        "                self.results[node_id] = result",
        "                self.result_queue.put((node_id, result))",
        "                processed_nodes.add(node_id)",
        "                self.execution_queue.task_done()",
        "            except queue.Empty:",
        "                break",
        "            except Exception as e:",
        "                self.execution_queue.task_done()",
        "",
        "    def get_node_by_id(self, node_id):",
        f"        agents = {workflow_data['agents']}",
        f"        tools = {workflow_data['tools']}",
        "        for agent in agents:",
        "            if agent['id'] == node_id:",
        "                return {**agent, 'type': 'agent'}",
        "        for tool in tools:",
        "            if tool['id'] == node_id:",
        "                return {**tool, 'type': 'tool'}",
        "        return None",
        "",
        "    def get_node_inputs(self, node_id, results):",
        "        inputs = {}",
        f"        connections = {workflow_data['connections']}",
        "        for conn in connections:",
        "            if conn['nodes'][1] == node_id:",
        "                source_id = conn['nodes'][0]",
        "                if source_id in results:",
        "                    inputs[conn['var2']] = results[source_id]",
        "        return inputs"
        "",
        "    def check_inputs_ready(self, node_id, inputs):",
        f"        connections = {workflow_data['connections']}",
        "        required_inputs = [conn['var2'] for conn in connections if conn['nodes'][1] == node_id]",
        "        return all(input_var in inputs for input_var in required_inputs)",
        "",
        "    def parse_tool_input(self, tool_name, user_message):",
        "        tool_function = self.tools[tool_name]",
        "        param_count = len(inspect.signature(tool_function).parameters)",
        "        if param_count == 0:",
        "            return []",
        "        inputs = user_message.split(',')",
        "        if len(inputs) != param_count:",
        "            raise ValueError(f'Expected {param_count} inputs, but got {len(inputs)}')",
        "        parsed_inputs = []",
        "        for input_value in inputs:",
        "            input_value = input_value.strip()",
        "            try:",
        "                if '.' in input_value:",
        "                    parsed_inputs.append(float(input_value))",
        "                else:",
        "                    parsed_inputs.append(int(input_value))",
        "            except ValueError:",
        "                parsed_inputs.append(input_value)",
        "        return parsed_inputs",
        "",
        "    def process_agent(self, agent, inputs):",
        f"        agent_data = {str({agent['name']: load_agent_data(agent['name']) for agent in workflow_data['agents']})}",
        "        agent_prompt = agent_data[agent['name']]['Agent Prompt']",
        "        for var, value in inputs.items():",
        "            agent_prompt = agent_prompt.replace('{' + var + '}', str(value))",
        "        model = genai.GenerativeModel(model_name=agent_data[agent['name']]['Model'])",
        "        chat = model.start_chat(history=[])",
        "        generation_config = genai.types.GenerationConfig(",
        "            temperature=agent_data[agent['name']]['Advanced Settings']['Temperature'],",
        "            top_p=agent_data[agent['name']]['Advanced Settings']['Top p'],",
        "            top_k=agent_data[agent['name']]['Advanced Settings']['Top k'],",
        "            max_output_tokens=agent_data[agent['name']]['Advanced Settings']['Max output length']",
        "        )",
        "        safety_settings = {",
        "            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,",
        "            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,",
        "            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,",
        "            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,",
        "        }",
        "        prompt = f'System: {agent_prompt}'",
        "        if 'user_message' in inputs:",
        "            prompt += f'\\nUser: {inputs[\"user_message\"]}'",
        "        response = chat.send_message(prompt, generation_config=generation_config, safety_settings=safety_settings)",
        "        return response.text.strip()",
        "",
        "    def process_tool(self, tool, inputs):",
        "        tool_function = self.tools[tool['name']]",
        "        if isinstance(inputs, dict):",
        "            parsed_inputs = {k: self.parse_value(v) for k, v in inputs.items()}",
        "            return tool_function(**parsed_inputs)",
        "        elif isinstance(inputs, list):",
        "            parsed_inputs = [self.parse_value(v) for v in inputs]",
        "            return tool_function(*parsed_inputs)",
        "        else:",
        "            return tool_function(self.parse_value(inputs))",
        "",
        "    def parse_value(self, value):",
        "        if isinstance(value, str):",
        "            value = value.strip()",
        "            try:",
        "                if '.' in value:",
        "                    return float(value)",
        "                else:",
        "                    return int(value)",
        "            except ValueError:",
        "                return value",
        "        return value",
        "",
        "    def topological_sort(self):",
        f"        graph = {{node['id']: set() for node in {workflow_data['agents'] + workflow_data['tools']}}}",
        f"        for conn in {workflow_data['connections']}:",
        "            graph[conn['nodes'][0]].add(conn['nodes'][1])",
        "        visited = set()",
        "        stack = []",
        "        def dfs(node):",
        "            visited.add(node)",
        "            for neighbor in graph[node]:",
        "                if neighbor not in visited:",
        "                    dfs(neighbor)",
        "            stack.append(node)",
        "        for node in graph:",
        "            if node not in visited:",
        "                dfs(node)",
        "        return stack[::-1]",
        "",
        "    def setup_tools(self):",
    ]
    
    # Add tool functions
    added_tools = set()
    for tool in workflow_data.get("tools", []):
        if tool["name"] not in added_tools:
            tool_data = load_tool_data(tool["name"])
            tool_code = tool_data["Tool Code"]
            function_name_match = tool_code.split("def ")[1].split("(")[0]
            indent = "        "
            indented_code = "\n".join(indent + line for line in tool_code.split("\n"))
            code_lines.extend([
                indented_code,
                f"        self.tools['{tool['name']}'] = {function_name_match}"
            ])
            added_tools.add(tool["name"])
    
    # Handle the case when there are no tools
    if not added_tools:
        code_lines.append("        pass")
        
    code_lines.extend([
        "",
        "def main():",
        "    app = WorkflowApp()",
        "    app.mainloop()",
        "",
        "if __name__ == '__main__':",
        "    main()"
    ])

    return "\n".join(code_lines)


def extract_imports(code):
    import_lines = []
    for line in code.split('\n'):
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            import_lines.append(line.strip())
    return import_lines

def extract_function_params(code):
    match = re.search(r'def\s+\w+\((.*?)\):', code)
    if match:
        params = match.group(1).split(',')
        return [param.strip().split('=')[0].strip() for param in params if param.strip()]
    return []

def extract_return_variables(code):
    match = re.search(r'return\s+(.*?)$', code, re.MULTILINE)
    if match:
        return_vars = match.group(1).split(',')
        return [var.strip() for var in return_vars if var.strip()]
    return []

def topological_sort(workflow_data):
    graph = {node["id"]: [] for node in workflow_data["agents"] + workflow_data["tools"]}
    for connection in workflow_data["connections"]:
        graph[connection["nodes"][0]].append(connection["nodes"][1])

    visited = set()
    stack = []

    def dfs(node):
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor)
        stack.append(node)

    for node in graph:
        if node not in visited:
            dfs(node)

    return stack[::-1]

def get_input_variables(node_id, workflow_data):
    input_vars = {}
    for connection in workflow_data["connections"]:
        if connection["nodes"][1] == node_id:
            input_vars[connection["var2"]] = f"results['{connection['nodes'][0]}']"
    if input_vars:
        return "{" + ", ".join(f"'{k}': {v}" for k, v in input_vars.items()) + "}"
    return None

def load_agent_data(agent_name):
    agents_file = r'agent_gen\saved_agents\agents.json'
    with open(agents_file, 'r') as f:
        agents = json.load(f)
    return next((agent for agent in agents if agent["Agent Name"] == agent_name), None)

def load_tool_data(tool_name):
    tools_file = r'agent_gen\saved_tools\tools.json'
    with open(tools_file, 'r') as f:
        tools = json.load(f)
    return next((tool for tool in tools if tool["Tool Name"] == tool_name), None)

def execute_workflow_code(workflow_code, update_output):
    try:
        with open(WORKFLOW_PY_PATH, 'w', encoding='utf-8') as file:
            file.write(workflow_code)
        
        update_output(f"Workflow code saved to: {WORKFLOW_PY_PATH}")

        python_executable = sys.executable

        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            if sys.platform == "win32":
                python_executable = os.path.join(sys.prefix, 'Scripts', 'python.exe')
            else:
                python_executable = os.path.join(sys.prefix, 'bin', 'python')

        process = subprocess.Popen([python_executable, WORKFLOW_PY_PATH],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   text=True,
                                   bufsize=1,
                                   universal_newlines=True,
                                   encoding='utf-8',
                                   errors='ignore')

        for line in process.stdout:
            update_output(line.strip())

        process.wait()
        if process.returncode != 0:
            update_output(f"Process exited with return code {process.returncode}")

    except Exception as e:
        update_output(f"An unexpected error occurred: {e}")

def generate_and_execute_workflow(workflow_data, update_output):
    workflow_code = generate_workflow_code(workflow_data)
    execute_workflow_code(workflow_code, update_output)