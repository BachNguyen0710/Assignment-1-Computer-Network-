# Assignment-1-Computer-Network-

Run the proxy, default port will be `8080`
```bash
python3 start_proxy.py --server-ip 127.0.0.1
```

Setup the conf file
```
host "192.168.56.103:8080" {

    proxy_pass http://192.168.56.103:9000;
}

host "app1.local" {
    proxy_pass http://192.168.56.103:9001;
    dist_policy round-robin
}

host "127.0.0.1:8080" {
    proxy_set_header Host $host;
    proxy_pass http://127.0.0.1:9000;
    proxy_pass http://127.0.0.1:9001;
    proxy_pass http://127.0.0.1:9002;
    dist_policy round-robin
}
```

As you can see here in the last hostname, it will be connecting to either of the 3 backends So you need to prepare (run in advanced) 3 backends and keep them alive
```bash
python3 start_sampleapp.py --server-ip 127.0.0.1 --server-port 9001
python3 start_sampleapp.py --server-ip 127.0.0.1 --server-port 9000
python3 start_sampleapp.py --server-ip 127.0.0.1 --server-port 9002
```
