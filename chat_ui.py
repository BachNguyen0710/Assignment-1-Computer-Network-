import sys
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
from queue import Queue
from p2p_handler_http import P2PHandler


class P2PChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("P2P Chat Client")
        self.root.geometry("600x500")

        self.message_queue = Queue()

        self.logic = P2PHandler(self.message_queue, api_url="http://192.168.1.204:8080")

        self.build_chat_ui()

        self.run_login_flow()

        if self.logic.my_username:
            self.display_message(f"[System] Welcome, {self.logic.my_username}!")
            # self.logic.start_listener()
            self.root.after(100, self.check_message_queue)
        else:
            self.root.destroy()
            sys.exit(0)

    def build_chat_ui(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(top_frame, text="Channel:").pack(side=tk.LEFT)
        self.channel_entry = tk.Entry(top_frame, width=15)
        self.channel_entry.insert(0, self.logic.current_channel)
        self.channel_entry.pack(side=tk.LEFT, padx=5)

        self.join_btn = tk.Button(
            top_frame, text="Join Channel", command=self.ui_join_channel
        )
        self.join_btn.pack(side=tk.LEFT, padx=5)

        self.dm_btn = tk.Button(
            top_frame, text="Send Direct Message", command=self.ui_show_dm_dialog
        )
        self.dm_btn.pack(side=tk.LEFT, padx=5)

        chat_frame = tk.Frame(self.root)
        chat_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame, state="disabled", wrap=tk.WORD
        )
        self.chat_display.pack(fill="both", expand=True)

        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill="x", padx=10, pady=10)

        self.msg_entry = tk.Entry(bottom_frame)
        self.msg_entry.pack(fill="x", side=tk.LEFT, expand=True, ipady=5)
        self.msg_entry.bind("<Return>", self.ui_send_broadcast)

        self.send_btn = tk.Button(
            bottom_frame, text="Broadcast", command=self.ui_send_broadcast
        )
        self.send_btn.pack(side=tk.LEFT, padx=5)

    def display_message(self, message):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, message + "\n\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see(tk.END)

    def ui_send_broadcast(self, event=None):
        message = self.msg_entry.get()
        if not message:
            return

        refresh = messagebox.askyesno(
            "Refresh Peers", "Refresh peer list from server first?"
        )
        self.msg_entry.delete(0, tk.END)

        threading.Thread(
            target=self.logic.broadcast_message, args=(message, refresh), daemon=True
        ).start()

    def ui_join_channel(self):
        new_channel = self.channel_entry.get()
        if not new_channel:
            messagebox.showerror("Error", "Please enter a channel name.")
            return

        threading.Thread(
            target=self.logic.join_channel, args=(new_channel,), daemon=True
        ).start()

    def ui_show_dm_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Direct Message")

        tk.Label(dialog, text="Target IP:").pack(pady=5)
        ip_entry = tk.Entry(dialog, width=40)
        ip_entry.pack(padx=10)

        tk.Label(dialog, text="Target Port:").pack(pady=5)
        port_entry = tk.Entry(dialog, width=40)
        port_entry.pack(padx=10)

        tk.Label(dialog, text="Message:").pack(pady=5)
        msg_entry = tk.Entry(dialog, width=40)
        msg_entry.pack(padx=10)

        def send_and_close():
            ip = ip_entry.get()
            port = port_entry.get()
            msg = msg_entry.get()

            if not ip or not port or not msg:
                messagebox.showerror("Error", "All fields are required.", parent=dialog)
                return

            formatted_message = f"(DM from {self.logic.my_username}): {msg}"

            threading.Thread(
                target=self.logic.send_p2p_message,
                args=(ip, port, formatted_message),
                daemon=True,
            ).start()

            self.display_message(f"[DM Sent to {ip}:{port}] {msg}")
            dialog.destroy()

        send_btn = tk.Button(dialog, text="Send Message", command=send_and_close)
        send_btn.pack(pady=10)
        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)

    def check_message_queue(self):
        while not self.message_queue.empty():
            try:
                message = self.message_queue.get_nowait()
                self.display_message(message)
            except Exception:
                pass

        self.root.after(100, self.check_message_queue)

    def run_login_flow(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Login & Register")
        dialog.geometry("300x250")

        tk.Label(dialog, text="Username:").pack(pady=5)
        user_entry = tk.Entry(dialog)
        user_entry.pack(padx=10, fill="x")

        tk.Label(dialog, text="Password:").pack(pady=5)
        pass_entry = tk.Entry(dialog, show="*")
        pass_entry.pack(padx=10, fill="x")

        tk.Label(dialog, text="Your P2P Port (e.g., 50001):").pack(pady=5)
        port_entry = tk.Entry(dialog)
        port_entry.pack(padx=10, fill="x")

        error_label = tk.Label(dialog, text="", fg="red")
        error_label.pack(pady=5)

        def on_login_click():
            username = user_entry.get()
            password = pass_entry.get()
            port_str = port_entry.get()

            if not username or not password or not port_str:
                error_label.config(text="All fields are required.")
                return

            try:
                port_num = int(port_str)
            except ValueError:
                error_label.config(text="Port must be a number.")
                return

            login_btn.config(text="Working...", state="disabled")

            try:
                self.logic.login_and_register(username, password, port_num)

                dialog.destroy()

            except Exception as e:
                error_label.config(text=str(e))
                login_btn.config(text="Login & Register", state="normal")

        login_btn = tk.Button(dialog, text="Login & Register", command=on_login_click)
        login_btn.pack(pady=20)

        dialog.transient(self.root)
        dialog.grab_set()
        self.root.wait_window(dialog)

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.logic.shutdown()
            self.root.destroy()
            sys.exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = P2PChatClient(root)

    if app.logic.my_username:
        root.mainloop()
