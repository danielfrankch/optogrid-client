# Setup on RPI 4B:

1. Install node
```
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

2. Launch WebApp
```
cd dashboard
node server.js
```

3. Use Chrome Browser to view the WebApp


- If viewing from the same machine, use the 
```
localhost:3000
```

- If viewing from other machine in the same local network, use the url provided in terminal following "Network Access"
for example 
```
172.168.156.233:3000
```