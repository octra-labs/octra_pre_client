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
  "priv": "d17116e015438f97649f46aa85d789876d0f3362fe2f6b4be6c36e94a0209ea2",
  "addr": "oct4B63TKwyP7jE2eqt7Rb3zs8FaeUns8ZfVvBPTC6gQf28",
  "rpc": "https://octra.network"
}
```

3. run

```bash
./run.sh       # on linux/mac
run.bat        # on windows
```
