
import socket
import struct
from time import sleep

import cv2
import numpy as np

# 配置
UDP_IP = "127.0.0.1"
UDP_PORT = 2345
BUFFER_SIZE = 1024
HEADER_SIZE = 4

frame_sequence = -1

def send_image(image, udp_socket):
    global frame_sequence

    file_size = len(image)
    num_packets = (file_size + BUFFER_SIZE - 1) // BUFFER_SIZE

    if frame_sequence < 245:
        frame_sequence += 1
    else:
        frame_sequence = 0

    # 发送图片
    for i in range(num_packets):
        start = i * BUFFER_SIZE
        end = min((i + 1) * BUFFER_SIZE, file_size)
        packet_data = image[start:end]
        last_packet_flag = 0x01 if i == num_packets - 1 else 0x00
        header = struct.pack('BBBB', 0xAA, frame_sequence, i, last_packet_flag)
        udp_socket.sendto(header + packet_data, (UDP_IP, UDP_PORT))

    return frame_sequence

def main():

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    cap = cv2.VideoCapture(0)
    if cap:
        while True:
            ret, frame = cap.read()
            cv2.imshow('frame', frame)

            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            result, imgencode = cv2.imencode('.jpg', frame, encode_param)
            data = np.array(imgencode).tobytes();

            send_image(data, udp_socket)

            if cv2.waitKey(1) == ord('q'):
                break

        cap.release()
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()