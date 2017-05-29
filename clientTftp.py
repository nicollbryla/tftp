#!/usr/bin/env python3

import socket
import sys
import hashlib


opc_rrq = b'\0\1'
opc_data = b'\0\3'
opc_ack = b'\0\4'
opc_err = b'\0\5'
opc_oack = b'\0\6'
max_val = 65536
default_blocksize = 512
windowsize = 16
everythingisok = True
rrqok = False
textfile = []
blocknumber = 1
lastnumber = 0
amountofpacket = 0

HOST = sys.argv[1]
PORT = int(sys.argv[2])
filename = sys.argv[3]
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.0)

packettosend = (opc_rrq + filename.encode('utf-8') + b'\0' + b'octet\0' + b'windowsize\0'
                + str(windowsize).encode('utf-8') + b'\0', (HOST, PORT))

while everythingisok:
    try:
        packet, client = sock.recvfrom(516)
    except socket.timeout:
        if rrqok:
            packettosend = (opc_ack + lastnumber.to_bytes(2, byteorder='big'), client)
        sock.sendto(*packettosend)
        continue

    opcode = packet[0:2]
    text = packet[4:]
    if opcode == opc_oack:
        rrqok = True
        windowsize = int(packet[2:].split(b'\0')[1])
        packettosend = (opc_ack + b'\0\0', client)
        sock.sendto(*packettosend)
    elif opcode == opc_err:
        everythingisok = False
        print('Error nr: ' + str(int.from_bytes(packet[2:4], byteorder='big')) + '. Message: ' + text.decode('utf-8')
              + '.')
        break
    elif opcode == opc_data:
        ifsendack = False
        actualdatanumber = int.from_bytes(packet[2:4], byteorder='big')
        if actualdatanumber == blocknumber:
            textfile.append(text)
            amountofpacket += 1
            lastnumber = blocknumber
            blocknumber += 1
            blocknumber %= max_val
            if amountofpacket == windowsize or len(text) < default_blocksize:
                ifsendack = True
        elif actualdatanumber > blocknumber:
            ifsendack = True
        elif blocknumber + windowsize > max_val and actualdatanumber < (blocknumber + windowsize) % max_val:
            ifsendack = True
        if ifsendack:
            amountofpacket = 0
            packettosend = (opc_ack + lastnumber.to_bytes(2, byteorder='big'), client)
            sock.sendto(*packettosend)
        if len(text) < default_blocksize:
            break

if everythingisok:
    texttomd5 = b''
    for i in range(len(textfile)):
        texttomd5 += textfile.pop(0)
    print('Md5 hash:', hashlib.md5(texttomd5).hexdigest())
