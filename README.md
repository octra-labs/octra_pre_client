# octra terminal client

a terminal wallet reminiscent of dos-era tui interfaces — but built with modern asynchronous architecture

## what it does

- shows your octra wallet balance and tx history  
- lets you send one or many transactions  
- exports your private key or full wallet file  

## works on

- linux  
- mac  
- windows (some features like clipboard may not work)

## what you need

- python 3.8 or higher  
- internet connection  
- your wallet file (private key)

## how to install and run (step by step)

1. open terminal  

2. run these commands one by one:

```bash
git clone https://github.com/octra-labs/octra_pre_client.git
cd octra_pre_client
python3 -m venv venv
source venv/bin/activate # for windows use: venv\Scripts\activate
pip install -r requirements.txt
cp wallet.json.example wallet.json
```

3. open wallet.json and edit it (change placeholders to your wallet data):

```json
{
  "priv": "private-key-here",
  "addr": "octxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "rpc": "https://octra.network"
}
```
You need use B64 type private key.

3. run

```bash
./run.sh       # on linux/mac
run.bat        # on windows
```
