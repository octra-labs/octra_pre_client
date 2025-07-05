# Octra Terminal Client

A simple and fast terminal wallet, reminiscent of DOS-era TUI interfaces, but built with a modern, asynchronous architecture.

## ✨ Key Features
* **View Balance & History**: Shows your Octra wallet balance and recent transaction history.
* **Send Transactions**: Lets you send transactions to a single address or multiple addresses.
* **Export Keys**: Allows you to export your private key or full wallet file.

## 💻 System Compatibility
* **Linux**
* **Mac**
* **Windows** (Note: some features like clipboard may not work)

---

## 🚀 Quick Start Guide

Follow the steps below to set up and run the application.

### 🧩 1. Initial Setup & System Requirements

Before you begin, ensure your system has:
* **Git** and **Python 3** (version 3.8 or higher).
* A stable **internet connection**.

Open your terminal and run this command to install the necessary packages (for Debian/Ubuntu-based Linux users):
```bash
sudo apt update && sudo apt install git python3 python3-venv -y
```

### 📥 2. Clone the Repository

Use `git` to download the project's source code to your computer.
```bash
git clone [https://github.com/Octra-Labs/octra-pre-client.git](https://github.com/Octra-Labs/octra-pre-client.git)
cd octra-pre-client
```

### 🛠️ 3. Set Up Environment & Install Dependencies

This step creates an isolated environment for the project to prevent conflicts.

1.  **Create and Activate the Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
    *Note for **Windows** users: use `venv\Scripts\activate`*

2.  **Install Required Libraries**
    This command reads the `requirements.txt` file and installs all necessary packages.
    ```bash
    pip install -r requirements.txt
    ```

### ⚙️ 4. Configure Your Wallet (IMPORTANT)

You cannot run the application until you have configured your wallet details.

1.  **Create the Configuration File**
    Copy the example file to create your personal configuration file.
    ```bash
    cp wallet.json.example wallet.json
    ```

2.  **Edit Your Wallet Details**
    Open `wallet.json` with a text editor and enter your information.
    ```json
    {
      "priv": "YOUR_PRIVATE_KEY_HERE",
      "addr": "YOUR_OCTRA_WALLET_ADDRESS_HERE",
      "rpc": "[https://octra.network](https://octra.network)"
    }
    ```
    * **`priv`**: Your secret private key. **NEVER SHARE THIS WITH ANYONE!**
    * **`addr`**: Your public wallet address, which starts with `oct...`.

### ✅ 5. Run the Application

Once all previous steps are complete, you are ready to run the client.

* To run the **standard client**:
  ```bash
  python3 cli.py
  ```

* To run the **v2 client** (which supports sending from a `.txt` file):
  ```bash
  python3 cliv2.py
  
