docker run --gpus all -it --rm --shm-size=8g -u $(id -u):$(id -g) -v $(pwd):/workspace mia-cifar-cu130
