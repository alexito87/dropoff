import socket

def find_free_ports(start=15672, end=15850):
    free_ports = []
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                free_ports.append(port)
            except OSError:
                continue
    return free_ports

if __name__ == "__main__":
    ports = find_free_ports()
    if ports:
        print("Свободные порты для RabbitMQ Management UI:", ports)
    else:
        print("Свободные порты в указанном диапазоне не найдены.")