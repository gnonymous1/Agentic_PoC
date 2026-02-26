import time

def process_data(data):
    # Inefficient loop
    result = []
    for i in range(len(data)):
        if data[i] % 2 == 0:
            result.append(data[i] * 2)
    return result

def main():
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    processed = process_data(data)
    print("Processed:", processed)
    
    # Unused variable
    x = 10
    
    # formatting issues
    y=[1,2,3]

if __name__ == "__main__":
    main()
