#!/usr/bin/env python3

import socket
import sys
import threading
from os import path

opc_rrq = b'\0\1'
opc_data = b'\0\3'
opc_ack = b'\0\4'
opc_err = b'\0\5'
err_ill = b'\0\5\0\4' + b'Illegal TFTP operation.\0'
opc_oack = b'\0\6'
max_val = 65536
default_blocksize = 512
trans_time_out = 2.0
windowsize = 16


class ServerTftp:
    def __init__(self, port, path, host, winsize):
        self.PORT = port
        self.PATH = path
        self.HOST = host
        self.WINDOWSIZE = winsize

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as msg:
            print("Exception socket.error : {0}".format(msg))

    def listen(self):
        try:
            self.sock.bind((self.HOST, self.PORT))
            self.sock.settimeout(None)
            while True:
                packet, client = self.sock.recvfrom(516)
                if packet[0:2] == opc_rrq:
                    filename, mode, windsize, blocks, unnecadd = packet[2:].split(b'\0')
                    if not path.isfile(self.PATH + '/' + filename.decode('utf-8')):
                        packet = (opc_err + b'\0\1' + b'File not found\0', client)
                        self.sock.sendto(*packet)
                        continue
                    if mode == b'octet' and windsize == b'windowsize' and max_val > int(blocks.decode('utf-8')) > 0:
                        Client(client, filename, min(int(blocks.decode('utf-8')), self.WINDOWSIZE), self.PATH).start()
                    else:
                        packet = (err_ill, client)
                        self.sock.sendto(*packet)
                else:
                    packet = (err_ill, client)
                    self.sock.sendto(*packet)
        finally:
            self.sock.close()


class Client(threading.Thread):
    def __init__(self, client, filename, blocks, path):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.CLIENT = client
        self.WINDOWSIZE = blocks
        self.PATH = path
        self.FILENAME = open(self.PATH + '/' + filename.decode('utf-8'), 'br')
        self.BLOCKNUMBER = 1
        self.LASTNUMBER = 0
        self.TEXTPCKG = []

    def run(self):
        try:
            self.sock.bind(('', 0))
            self.sock.settimeout(trans_time_out)
            i = 6
            while i > 0:
                packettosend = (opc_oack + b'windowsize\0' + str(self.WINDOWSIZE).encode('utf-8') + b'\0', self.CLIENT)
                self.sock.sendto(*packettosend)
                try:
                    packet, client = self.sock.recvfrom(4)
                    if packet == opc_ack + b'\0\0':
                        break
                    elif packet[0:2] == opc_err:
                        return
                except socket.timeout:
                    i -= 1
                    self.sock.sendto(*packettosend)
            if i == 0:
                print("Negotiation went wrong.")
                return
            lasttoread = False
            while True:
                while len(self.TEXTPCKG) < self.WINDOWSIZE:
                    if lasttoread:
                        break
                    text = self.FILENAME.read(default_blocksize)
                    self.TEXTPCKG.append(text)
                    if len(text) < default_blocksize:
                        lasttoread = True
                        break
                if not self.TEXTPCKG:
                    print("Full success! Juuuhu")
                    break
                for i in range(len(self.TEXTPCKG)):
                    packettosend = (
                        opc_data + ((self.BLOCKNUMBER + i) % max_val).to_bytes(2, byteorder='big') + self.TEXTPCKG[i],
                        self.CLIENT)
                    self.sock.sendto(*packettosend)
                i = 0
                while i != 7:
                    try:
                        packet, client = self.sock.recvfrom(4)
                        number_ackpack = int.from_bytes(packet[2:4], byteorder='big')
                        if number_ackpack == self.LASTNUMBER:
                            self.BLOCKNUMBER = number_ackpack
                            break
                        if number_ackpack >= self.BLOCKNUMBER:
                            amountpacktodelete = number_ackpack - self.BLOCKNUMBER + 1
                        else:
                            amountpacktodelete = number_ackpack - self.BLOCKNUMBER + 1 + max_val
                        for j in range(amountpacktodelete):
                            self.TEXTPCKG.pop(0)
                        self.BLOCKNUMBER = number_ackpack
                        break
                    except socket.timeout:
                        i += 1
                        for j in range(len(self.TEXTPCKG)):
                            packettosend = (
                                opc_data + ((self.BLOCKNUMBER + i) % max_val).to_bytes(2, byteorder='big') +
                                self.TEXTPCKG[i], self.CLIENT)
                            self.sock.sendto(*packettosend)
                else:
                    print("Communication went wrong.")
                    return
                self.LASTNUMBER = self.BLOCKNUMBER
                self.BLOCKNUMBER += 1
                self.BLOCKNUMBER %= max_val
        finally:
            self.sock.close()


port = int(sys.argv[1])
path_in = sys.argv[2]
host = "localhost"
server = ServerTftp(port, path_in, host, windowsize)
server.listen()
