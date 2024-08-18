# ✨ LXC AutoScale ML

> ongoing update..

### LXC AutoScale API

If You want to have **full control**, **precise thresholds** and consider the **integration with your existing setup** please use the LXC AutoScale API, a simple API HTTP interface to perform all common scaling operations with just few, simple, `curl` requests.



### LXC Monitor
In the `monitor` folder you will find all files needed to run a lightweight LXC monitor service to generate the needed data to train the machine learning model.

### LXC AutoScale ML
In the `/usr/local/bin/autoscaleapi` folder you will find all files needed to run the machine learning model. It will take decision against using the AutoScale API. The model is updated every cycle and  can be run in dry-run mode (--dry-run) to check its decisions before to change real-world resources.

I will add accurate documentation in then next days.

