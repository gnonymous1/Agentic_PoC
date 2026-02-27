import unittest
from unittest.mock import MagicMock, patch
import sys
import shlex
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock modules
sys.modules['pyautogui'] = MagicMock()
sys.modules['pygetwindow'] = MagicMock()
sys.modules['winreg'] = MagicMock()
sys.modules['cortex'] = MagicMock()
sys.modules['cortex.llm'] = MagicMock()
sys.modules['hippocampus'] = MagicMock()
sys.modules['hippocampus.memory'] = MagicMock()

# Mock tool decorator
mock_tool = MagicMock()
def tool_decorator(func):
    return func
mock_tool.tool = tool_decorator
sys.modules['langchain_core'] = mock_tool
sys.modules['langchain_core.tools'] = mock_tool
sys.modules['langchain_core.messages'] = MagicMock()

# Import the module under test
# We need to reload it because it caches `sys.platform` logic if defined at module level (but it's inside function)
from agent_fabric.computer_tools import computer_open_app

class TestComputerToolsSafe(unittest.TestCase):

    @patch('agent_fabric.computer_tools.subprocess.Popen')
    @patch('sys.platform', 'linux')
    def test_open_app_linux(self, mock_popen):
        # On Linux, shlex uses posix=True

        # 1. Simple command
        computer_open_app("notepad")
        mock_popen.assert_called_with(['notepad'], shell=False)

        # 2. Command with args
        computer_open_app("notepad file.txt")
        mock_popen.assert_called_with(['notepad', 'file.txt'], shell=False)

        # 3. Quoted args (stripped by shlex posix=True)
        computer_open_app('notepad "file with spaces.txt"')
        mock_popen.assert_called_with(['notepad', 'file with spaces.txt'], shell=False)

        # 4. Command injection attempt
        computer_open_app("echo pwned > pwned.txt")
        # shlex.split("echo pwned > pwned.txt") -> ['echo', 'pwned', '>', 'pwned.txt']
        mock_popen.assert_called_with(['echo', 'pwned', '>', 'pwned.txt'], shell=False)

    @patch('agent_fabric.computer_tools.subprocess.Popen')
    @patch('sys.platform', 'win32')
    def test_open_app_windows(self, mock_popen):
        # On Windows, shlex uses posix=False

        # 1. Simple command
        computer_open_app("notepad")
        mock_popen.assert_called_with(['notepad'], shell=False)

        # 2. Command with args
        computer_open_app("notepad file.txt")
        mock_popen.assert_called_with(['notepad', 'file.txt'], shell=False)

        # 3. Quoted args (preserved by shlex posix=False, then stripped by our logic)
        computer_open_app('notepad "file with spaces.txt"')
        # shlex(posix=False) -> ['notepad', '"file with spaces.txt"']
        # stripped -> ['notepad', 'file with spaces.txt']
        mock_popen.assert_called_with(['notepad', 'file with spaces.txt'], shell=False)

        # 4. Command injection attempt
        computer_open_app("echo pwned > pwned.txt")
        # shlex(posix=False) -> ['echo', 'pwned', '>', 'pwned.txt']
        mock_popen.assert_called_with(['echo', 'pwned', '>', 'pwned.txt'], shell=False)

        # 5. Windows path with backslashes
        computer_open_app(r'notepad C:\Users\test\file.txt')
        # shlex(posix=False) -> ['notepad', 'C:\\Users\\test\\file.txt']
        mock_popen.assert_called_with(['notepad', r'C:\Users\test\file.txt'], shell=False)

    @patch('agent_fabric.computer_tools.subprocess.Popen')
    @patch('sys.platform', 'win32')
    def test_open_app_windows_quoted_path(self, mock_popen):
        # Windows path with spaces inside quotes
        cmd = r'notepad "C:\Program Files\App\bin.exe"'
        computer_open_app(cmd)
        # shlex(posix=False) -> ['notepad', '"C:\\Program Files\\App\\bin.exe"']
        # stripped -> ['notepad', 'C:\\Program Files\\App\\bin.exe']
        mock_popen.assert_called_with(['notepad', r'C:\Program Files\App\bin.exe'], shell=False)

if __name__ == '__main__':
    unittest.main()
