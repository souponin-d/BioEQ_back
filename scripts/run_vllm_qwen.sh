#!/bin/bash

export CUDA_VISIBLE_DEVICES=0,1

vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 127.0.0.1 --port 8000 \
  --api-key local \
  --dtype auto \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.90
