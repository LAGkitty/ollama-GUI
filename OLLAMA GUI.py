import tkinter as tk
from tkinter import ttk, scrolledtext, font
import requests
import json
import threading
import time
import sys
import os

class ModernOllamaChat:
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama Chat")
        self.root.geometry("900x700")
        
        # Set theme colors
        self.bg_color = "#f5f5f5"
        self.accent_color = "#4a86e8"
        self.chat_bg = "#ffffff"
        self.user_bubble_color = "#e1f5fe"
        self.ai_bubble_color = "#f5f5f5"
        self.text_color = "#333333"
        
        # Configure the root window
        self.root.configure(bg=self.bg_color)
        
        # Create custom fonts
        self.default_font = font.nametofont("TkDefaultFont").copy()
        self.chat_font = font.Font(family=self.default_font.cget("family"), size=10)
        self.header_font = font.Font(family=self.default_font.cget("family"), size=14, weight="bold")
        
        # Apply theme to ttk widgets
        style = ttk.Style()
        style.configure("TFrame", background=self.bg_color)
        style.configure("Chat.TFrame", background=self.chat_bg)
        style.configure("TButton", 
                       background=self.accent_color, 
                       foreground="white", 
                       padding=6,
                       font=self.default_font)
        style.map("TButton",
                 background=[('active', '#3a70c7'), ('disabled', '#cccccc')])
        
        # Set up the main layout
        self.setup_layout()
        
        # Initialize conversation history
        self.conversation_history = []
        
        # Get available models
        self.available_models = self.get_available_models()
        for model in self.available_models:
            self.model_combobox['values'] = (*self.model_combobox['values'], model)
        
        # Select the first model by default, or fallback to a default if none available
        if self.available_models and len(self.available_models) > 0:
            self.model_combobox.current(0)
        else:
            self.model_combobox.set("gemma3:1b")  # Default fallback
        
        # Set up a flag for tracking if a request is in progress
        self.is_generating = False
        
        # Set up streaming response cache
        self.current_response = ""
        
        # Show welcome message
        self.show_welcome_message()
    
    def setup_layout(self):
        # Main container
        main_frame = ttk.Frame(self.root, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header area
        header_frame = ttk.Frame(main_frame, style="TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title
        title_label = ttk.Label(header_frame, 
                               text="Ollama Chat", 
                               font=self.header_font, 
                               background=self.bg_color,
                               foreground=self.accent_color)
        title_label.pack(side=tk.LEFT)
        
        # Model selection
        model_frame = ttk.Frame(header_frame, style="TFrame")
        model_frame.pack(side=tk.RIGHT)
        
        model_label = ttk.Label(model_frame, 
                               text="Model:", 
                               background=self.bg_color)
        model_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.model_combobox = ttk.Combobox(model_frame, width=20, state="readonly")
        self.model_combobox.pack(side=tk.LEFT)
        
        # Chat area with messages
        self.chat_frame = ttk.Frame(main_frame, style="Chat.TFrame")
        self.chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create a canvas and scrollbar for the chat frame
        self.chat_canvas = tk.Canvas(self.chat_frame, bg=self.chat_bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.chat_frame, orient="vertical", command=self.chat_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.chat_canvas, style="Chat.TFrame")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )
        
        self.chat_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=self.chat_canvas.winfo_reqwidth())
        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # When the chat canvas is resized, update the scrollable frame width
        self.chat_canvas.bind("<Configure>", self.on_canvas_configure)
        
        # Input area
        input_frame = ttk.Frame(main_frame, style="TFrame")
        input_frame.pack(fill=tk.X)
        
        # Text input with multiple lines
        self.input_text = scrolledtext.ScrolledText(input_frame, 
                                                  height=3, 
                                                  font=self.chat_font,
                                                  wrap=tk.WORD)
        self.input_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.input_text.bind("<Shift-Return>", lambda e: None)  # Allow for newline with Shift+Enter
        self.input_text.bind("<Return>", self.on_send)  # Send message with Enter
        
        # Send button
        self.send_button = ttk.Button(input_frame, 
                                     text="Send", 
                                     command=self.on_send,
                                     style="TButton")
        self.send_button.pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, 
                              textvariable=self.status_var, 
                              background="#f0f0f0", 
                              relief=tk.SUNKEN, 
                              anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Focus on the input field
        self.input_text.focus_set()
    
    def on_canvas_configure(self, event):
        # Update the width of the window inside the canvas when the canvas is resized
        self.chat_canvas.itemconfig("win", width=event.width)
        
        # Ensure the scrollable_frame width matches the canvas width
        self.chat_canvas.itemconfig(
            self.chat_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", tags="win"),
            width=event.width
        )
    
    def get_available_models(self):
        """Get the list of available models from Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except requests.exceptions.RequestException:
            self.status_var.set("Could not connect to Ollama. Check if it's running.")
            return []
    
    def show_welcome_message(self):
        """Show a welcome message in the chat"""
        welcome_message = "Welcome to Ollama Chat! Type a message to start chatting with the AI."
        
        # Create a frame for the message
        message_frame = ttk.Frame(self.scrollable_frame, style="Chat.TFrame")
        message_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add the AI message with system styling
        message_bubble = ttk.Frame(message_frame, style="Chat.TFrame")
        message_bubble.pack(fill=tk.X, padx=(0, 50), anchor=tk.W)
        
        # Add a thin border and background color
        message_text = tk.Text(message_bubble, 
                              wrap=tk.WORD,
                              font=self.chat_font,
                              bg=self.ai_bubble_color,
                              relief=tk.SOLID,
                              borderwidth=1,
                              padx=10,
                              pady=10,
                              height=3)
        message_text.pack(fill=tk.X, padx=0, pady=0)
        message_text.insert(tk.END, welcome_message)
        message_text.config(state=tk.DISABLED)
        
        # Adjust the height to fit the content
        message_text.update_idletasks()
        lines = int(message_text.index('end-1c').split('.')[0])
        message_text.config(height=lines)
        
        # Add a small attribution label
        attribution = ttk.Label(message_frame, 
                               text="Ollama", 
                               background=self.chat_bg,
                               foreground="#999999",
                               font=(self.default_font.cget("family"), 8))
        attribution.pack(anchor=tk.W, padx=5, pady=(2, 5))
        
        # Scroll to bottom
        self.scroll_to_bottom()
    
    def on_send(self, event=None):
        """Handle send button click or Enter key"""
        # Get the message text
        message = self.input_text.get("1.0", tk.END).strip()
        
        # Don't send empty messages
        if not message or self.is_generating:
            return "break"  # Prevent default Enter behavior
        
        # Clear the input field
        self.input_text.delete("1.0", tk.END)
        
        # Add user message to the chat
        self.add_user_message(message)
        
        # Create a placeholder for the AI response
        ai_response_frame = self.add_ai_message_placeholder()
        
        # Disable send button during generation
        self.is_generating = True
        self.send_button.config(state=tk.DISABLED)
        self.status_var.set("AI is thinking...")
        
        # Start a thread to handle the API call
        threading.Thread(target=self.generate_response, 
                        args=(message, ai_response_frame), 
                        daemon=True).start()
        
        return "break"  # Prevent default Enter behavior
    
    def add_user_message(self, message):
        """Add a user message bubble to the chat"""
        # Create a frame for the message
        message_frame = ttk.Frame(self.scrollable_frame, style="Chat.TFrame")
        message_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add the user message with styling
        message_bubble = ttk.Frame(message_frame, style="Chat.TFrame")
        message_bubble.pack(fill=tk.X, padx=(50, 0), anchor=tk.E)
        
        # Add user message with styling
        message_text = tk.Text(message_bubble, 
                              wrap=tk.WORD, 
                              font=self.chat_font,
                              bg=self.user_bubble_color,
                              relief=tk.SOLID,
                              borderwidth=1,
                              padx=10,
                              pady=10,
                              height=3)
        message_text.pack(fill=tk.X, padx=0, pady=0)
        message_text.insert(tk.END, message)
        message_text.config(state=tk.DISABLED)
        
        # Adjust the height to fit the content
        message_text.update_idletasks()
        lines = int(message_text.index('end-1c').split('.')[0])
        message_text.config(height=lines)
        
        # Add a small attribution label
        attribution = ttk.Label(message_frame, 
                               text="You", 
                               background=self.chat_bg,
                               foreground="#999999",
                               font=(self.default_font.cget("family"), 8))
        attribution.pack(anchor=tk.E, padx=5, pady=(2, 5))
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Scroll to bottom
        self.scroll_to_bottom()
    
    def add_ai_message_placeholder(self):
        """Add a placeholder for the AI message that will be updated as tokens arrive"""
        # Create a frame for the message
        message_frame = ttk.Frame(self.scrollable_frame, style="Chat.TFrame")
        message_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add the AI message container
        message_bubble = ttk.Frame(message_frame, style="Chat.TFrame")
        message_bubble.pack(fill=tk.X, padx=(0, 50), anchor=tk.W)
        
        # Create the message text widget that will be updated
        message_text = tk.Text(message_bubble, 
                              wrap=tk.WORD,
                              font=self.chat_font,
                              bg=self.ai_bubble_color,
                              relief=tk.SOLID,
                              borderwidth=1,
                              padx=10,
                              pady=10,
                              height=1)
        message_text.pack(fill=tk.X, padx=0, pady=0)
        message_text.insert(tk.END, "▎")  # Cursor placeholder
        
        # Add a small attribution label
        attribution = ttk.Label(message_frame, 
                               text="Ollama", 
                               background=self.chat_bg,
                               foreground="#999999",
                               font=(self.default_font.cget("family"), 8))
        attribution.pack(anchor=tk.W, padx=5, pady=(2, 5))
        
        # Scroll to bottom
        self.scroll_to_bottom()
        
        return message_text
    
    def update_ai_message(self, message_widget, text):
        """Update the AI message with new text"""
        message_widget.config(state=tk.NORMAL)
        message_widget.delete("1.0", tk.END)
        message_widget.insert(tk.END, text + "▎")  # Add cursor effect
        
        # Adjust the height to fit the content
        message_widget.update_idletasks()
        lines = int(message_widget.index('end-1c').split('.')[0])
        message_widget.config(height=max(1, lines))
        
        # Scroll to bottom
        self.scroll_to_bottom()
    
    def finalize_ai_message(self, message_widget, text):
        """Finalize the AI message by removing the cursor and disabling the widget"""
        message_widget.config(state=tk.NORMAL)
        message_widget.delete("1.0", tk.END)
        message_widget.insert(tk.END, text)
        
        # Adjust the height to fit the content
        message_widget.update_idletasks()
        lines = int(message_widget.index('end-1c').split('.')[0])
        message_widget.config(height=lines)
        message_widget.config(state=tk.DISABLED)
        
        # Add to conversation history
        self.conversation_history.append({"role": "assistant", "content": text})
        
        # Scroll to bottom
        self.scroll_to_bottom()
    
    def generate_response(self, user_message, response_widget):
        """Generate a response from the API with streaming"""
        try:
            # Get the selected model
            model = self.model_combobox.get()
            
            # Create a system message for chat context
            system_message = "You are a helpful AI assistant. Be concise and straightforward in your responses."
            
            # Reset the current response
            self.current_response = ""
            
            # Set up streaming request to Ollama API
            url = "http://localhost:11434/api/generate"
            
            data = {
                "model": model,
                "prompt": user_message,
                "system": system_message,
                "stream": True,
                "options": {
                    "temperature": 0.7
                }
            }
            
            # Send the streaming request
            response = requests.post(url, json=data, stream=True)
            
            if response.status_code == 200:
                # Process the streaming response
                for line in response.iter_lines():
                    if line:
                        json_line = json.loads(line)
                        # Check if this is the final message
                        if json_line.get("done", False):
                            # Finalize the message
                            self.finalize_ai_message(response_widget, self.current_response)
                            break
                        
                        # Append the response token
                        token = json_line.get("response", "")
                        self.current_response += token
                        
                        # Update the UI with the current response text
                        self.root.after(0, lambda: self.update_ai_message(response_widget, self.current_response))
                        
                        # Small sleep to make the streaming visible
                        time.sleep(0.01)
            else:
                error_message = f"Error: HTTP {response.status_code}"
                self.finalize_ai_message(response_widget, error_message)
        
        except requests.exceptions.ConnectionError:
            error_message = "Could not connect to Ollama. Make sure it's running."
            self.finalize_ai_message(response_widget, error_message)
        
        except Exception as e:
            error_message = f"Error: {str(e)}"
            self.finalize_ai_message(response_widget, error_message)
        
        finally:
            # Reset UI state
            self.is_generating = False
            self.root.after(0, lambda: self.reset_ui_state())
    
    def reset_ui_state(self):
        """Reset UI elements after generation completes"""
        self.send_button.config(state=tk.NORMAL)
        self.status_var.set("Ready")
        self.input_text.focus_set()
    
    def scroll_to_bottom(self):
        """Scroll the chat view to the bottom"""
        self.chat_canvas.update_idletasks()
        self.chat_canvas.config(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

if __name__ == "__main__":
    # Check if Ollama is available
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
    except requests.exceptions.RequestException:
        print("Warning: Could not connect to Ollama. Make sure it's running.")
        print("The application will start, but you need Ollama running to chat.")
    
    # Check for required packages
    try:
        import requests
    except ImportError:
        print("Missing dependency: requests")
        print("Please install it with: pip install requests")
        sys.exit(1)
        
    # Start the application
    root = tk.Tk()
    app = ModernOllamaChat(root)
    root.mainloop()