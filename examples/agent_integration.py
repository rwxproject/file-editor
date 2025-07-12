#!/usr/bin/env python3
"""Example showing how to integrate file-editor with AI agents."""

import tempfile
import json
from file_editor import AgentFileSystem, SpecializedAgentEditors


class SimpleAIAgent:
    """A simple AI agent that can edit files safely."""
    
    def __init__(self, workspace_dir: str):
        """Initialize agent with workspace."""
        self.fs = AgentFileSystem(workspace_dir)
        self.specialized = SpecializedAgentEditors(self.fs)
        
    def read_file_safely(self, file_path: str, max_lines: int = 1000) -> str:
        """Read file with safety limits."""
        if not self.fs.file_exists(file_path):
            return f"Error: File '{file_path}' does not exist"
            
        file_info = self.fs.get_file_info(file_path)
        if file_info and file_info['size'] > 10 * 1024 * 1024:  # 10MB limit
            return f"Error: File '{file_path}' is too large ({file_info['size']} bytes)"
            
        content = self.fs.read_full_file(file_path, max_lines=max_lines)
        return content or f"Error: Could not read file '{file_path}'"
        
    def edit_file_section(self, file_path: str, start_line: int, end_line: int, 
                         new_content: str) -> str:
        """Edit a specific section of a file."""
        if not self.fs.file_exists(file_path):
            return f"Error: File '{file_path}' does not exist"
            
        success = self.fs.modify_file_section(file_path, start_line, end_line, new_content)
        if success:
            return f"Successfully modified lines {start_line}-{end_line} in '{file_path}'"
        else:
            return f"Error: Failed to modify '{file_path}'"
            
    def search_and_replace(self, file_path: str, search_term: str, 
                          replacement: str) -> str:
        """Search for text and replace it."""
        if not self.fs.file_exists(file_path):
            return f"Error: File '{file_path}' does not exist"
            
        # First, find all occurrences
        results = self.fs.search_in_file(file_path, search_term)
        
        if not results:
            return f"No occurrences of '{search_term}' found in '{file_path}'"
            
        # For safety, let's limit to files with reasonable number of matches
        if len(results) > 50:
            return f"Too many matches ({len(results)}) - please be more specific"
            
        # Read file and perform replacement
        content = self.fs.read_full_file(file_path)
        if content is None:
            return f"Error: Could not read '{file_path}'"
            
        new_content = content.replace(search_term, replacement)
        
        # Create backup and write new content
        success = self.fs.create_file(f"{file_path}.backup", content)
        if not success:
            return f"Error: Could not create backup of '{file_path}'"
            
        # Overwrite original with new content
        self.fs.delete_file(file_path)
        success = self.fs.create_file(file_path, new_content)
        
        if success:
            return f"Replaced {len(results)} occurrences of '{search_term}' with '{replacement}'"
        else:
            return f"Error: Failed to write changes to '{file_path}'"
            
    def create_markdown_document(self, file_path: str, title: str, 
                                sections: list[dict]) -> str:
        """Create a new markdown document with specified sections."""
        if self.fs.file_exists(file_path):
            return f"Error: File '{file_path}' already exists"
            
        # Create initial document
        content = f"# {title}\n\n"
        success = self.fs.create_file(file_path, content)
        
        if not success:
            return f"Error: Could not create '{file_path}'"
            
        # Add sections using specialized markdown editor
        for section in sections:
            section_title = section.get('title', 'Untitled')
            section_content = section.get('content', '')
            level = section.get('level', 2)
            
            success = self.specialized.markdown_edit_section(file_path, section_title, section_content)
            if not success:
                # Section doesn't exist, so insert it
                from file_editor.formats.markdown import MarkdownEditor
                full_path = self.fs._validate_path(file_path)
                editor = MarkdownEditor(full_path)
                editor.insert_section(section_title, section_content, level)
                
        return f"Created markdown document '{file_path}' with {len(sections)} sections"
        
    def analyze_code_file(self, file_path: str) -> str:
        """Analyze a code file and provide basic metrics."""
        if not self.fs.file_exists(file_path):
            return f"Error: File '{file_path}' does not exist"
            
        file_info = self.fs.get_file_info(file_path)
        if not file_info or not file_info.get('is_text', False):
            return f"Error: '{file_path}' is not a text file"
            
        stats = self.fs.get_file_stats(file_path)
        if not stats:
            return f"Error: Could not analyze '{file_path}'"
            
        # Get additional code-specific metrics
        content = self.fs.read_full_file(file_path)
        if not content:
            return f"Error: Could not read '{file_path}'"
            
        lines = content.split('\n')
        
        # Count different types of lines
        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            elif stripped.startswith('#') or stripped.startswith('//'):
                comment_lines += 1
            else:
                code_lines += 1
                
        analysis = {
            'total_lines': stats['lines'],
            'code_lines': code_lines,
            'comment_lines': comment_lines,
            'blank_lines': blank_lines,
            'words': stats['words'],
            'characters': stats['characters'],
            'file_size': file_info['size']
        }
        
        return f"Code analysis for '{file_path}':\n" + json.dumps(analysis, indent=2)
        
    def get_operation_history(self) -> str:
        """Get history of operations performed."""
        log = self.fs.get_operation_log()
        
        if not log:
            return "No operations performed yet"
            
        recent_ops = log[-10:]  # Last 10 operations
        history = "Recent operations:\n"
        
        for i, op in enumerate(recent_ops, 1):
            operation = op['operation']
            file_path = op['file']
            details = op['details']
            
            history += f"{i}. {operation} on '{file_path}' - {details}\n"
            
        return history


def demonstrate_agent_usage():
    """Demonstrate how an AI agent might use the file editor."""
    print("=== AI Agent File Editing Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize agent
        agent = SimpleAIAgent(temp_dir)
        
        # Scenario 1: Create a project README
        print("\n1. Creating project README...")
        sections = [
            {
                'title': 'Installation',
                'content': 'Install the package using pip:\n\n```bash\npip install file-editor\n```',
                'level': 2
            },
            {
                'title': 'Quick Start',
                'content': 'Here\'s how to get started:\n\n```python\nfrom file_editor import AgentFileSystem\nfs = AgentFileSystem("workspace")\n```',
                'level': 2
            },
            {
                'title': 'Features',
                'content': '- Memory-efficient file editing\n- Agent-friendly API\n- Support for multiple file formats\n- Safe concurrent access',
                'level': 2
            }
        ]
        
        result = agent.create_markdown_document("README.md", "File Editor Library", sections)
        print(result)
        
        # Scenario 2: Read and analyze the created file
        print("\n2. Reading created file...")
        content = agent.read_file_safely("README.md")
        print(f"File content preview (first 200 chars):\n{content[:200]}...")
        
        # Scenario 3: Edit a section
        print("\n3. Updating installation section...")
        new_installation = """Install the package using your preferred method:

**Using pip:**
```bash
pip install file-editor
```

**Using uv:**
```bash
uv add file-editor
```

**From source:**
```bash
git clone https://github.com/example/file-editor.git
cd file-editor
uv sync
```"""
        
        result = agent.edit_file_section("README.md", 4, 8, new_installation)
        print(result)
        
        # Scenario 4: Create a Python code file
        print("\n4. Creating Python example...")
        python_code = '''#!/usr/bin/env python3
"""Example usage of file-editor library."""

from file_editor import AgentFileSystem

def main():
    # Create file system interface
    fs = AgentFileSystem("my_workspace")
    
    # Create a new file
    fs.create_file("example.txt", "Hello, World!")
    
    # Read the file
    content = fs.read_full_file("example.txt")
    print(f"File content: {content}")
    
    # Modify part of the file
    fs.modify_file_section("example.txt", 1, 1, "Hello, File Editor!")
    
    print("File editing completed successfully!")

if __name__ == "__main__":
    main()
'''
        
        agent.fs.create_file("example.py", python_code)
        print("Created example.py")
        
        # Scenario 5: Analyze the code file
        print("\n5. Analyzing code file...")
        analysis = agent.analyze_code_file("example.py")
        print(analysis)
        
        # Scenario 6: Search and replace in code
        print("\n6. Updating code...")
        result = agent.search_and_replace("example.py", "Hello, World!", "Hello, Universe!")
        print(result)
        
        # Scenario 7: Create a CSV data file
        print("\n7. Creating CSV data...")
        csv_data = """name,age,department,salary
Alice Johnson,28,Engineering,75000
Bob Smith,35,Marketing,68000
Carol Davis,31,Engineering,82000
David Wilson,29,Sales,59000
Eve Brown,33,Engineering,78000
"""
        agent.fs.create_file("employees.csv", csv_data)
        
        # Filter high-salary engineers
        result = agent.specialized.csv_filter_rows(
            "employees.csv", 
            "department", 
            "Engineering",
            "engineers.csv"
        )
        
        if result:
            print(f"Filtered engineers to: {result}")
            
        # Scenario 8: Show operation history
        print("\n8. Operation history...")
        history = agent.get_operation_history()
        print(history)
        
        # Scenario 9: Demonstrate safety features
        print("\n9. Testing safety features...")
        
        # Try to access file outside workspace (should fail)
        result = agent.read_file_safely("../../../etc/passwd")
        print(f"Attempting to read outside workspace: {result}")
        
        # Try to read non-existent file
        result = agent.read_file_safely("nonexistent.txt")
        print(f"Reading non-existent file: {result}")
        
        print("\n=== Demo completed successfully! ===")


if __name__ == "__main__":
    demonstrate_agent_usage()