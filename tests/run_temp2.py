import time

def handler(payload: str):
    print(payload)
    print(payload['data'])
    i = 0
    sum = 0
    while (i < 100000):
        sum += i
        i += 1

    print(sum)

