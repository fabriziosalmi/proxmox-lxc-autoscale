# LXC AutoScale UI 

To run your Flask application, follow these steps:

### 1. Set Up Your Environment

1. **Install Dependencies**:
   Make sure you have Flask and Flask-SocketIO installed. You can install them using `pip`:
   ```bash
   pip install flask flask-socketio
   ```

2. **Ensure Your Python Environment Is Set Up**:
   Make sure you are in the correct Python environment (e.g., a virtual environment) where Flask and Flask-SocketIO are installed.

### 2. Place Your Files Correctly

Ensure your file structure is set up like this:

```plaintext
/lxc_autoscale_ui/
│
├── lxc_autoscale_ui.py
├── templates/
│   └── index.html
└── static/
    └── styles.css
```

### 3. Run the Application

1. **Navigate to the Directory**:
   Use the terminal to navigate to the directory containing your `lxc_autoscale_ui.py` script:
   ```bash
   cd /usr/local/bin/lxc_autoscale_ui
   ```

2. **Run the Flask Application**:
   Run the Python script using the command:
   ```bash
   python3 lxc_autoscale_ui.py
   ```
   This command will start the Flask server on `http://0.0.0.0:5000`.

### 4. Access the Application

1. **Open Your Web Browser**:
   Visit `http://<your-proxmox-ip>:5000/` in your web browser. Replace `<your-proxmox-ip>` with your Proxmox server's IP address. If you are running this on your local machine, you can use `http://127.0.0.1:5000/`.

2. **View the Dashboard**:
   You should now see the Resource Scaling Dashboard in your browser.

### 5. Troubleshooting

- **Port Conflicts**: If port `5000` is already in use, you can change the port in the `socketio.run()` function:
  ```python
  socketio.run(app, host='0.0.0.0', port=5050, debug=True)
  ```

- **Firewall Issues**: Ensure that your server's firewall allows incoming connections on port `5000`.

### 6. Stopping the Server

To stop the Flask server, simply press `Ctrl + C` in the terminal where the server is running.

This will terminate the process and stop the server.
