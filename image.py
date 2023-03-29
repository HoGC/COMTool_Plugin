'''
    @brief This is an example plugin, can receive and send data
    @author
    @date
    @license LGPL-3.0
'''
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import struct
import time
import numpy as np
from collections import defaultdict
import io
from PIL import Image, ImageDraw, ImageFont


try:
    from plugins.base import Plugin_Base
    from conn import ConnectionStatus
    from i18n import _
except ImportError:
    from COMTool.plugins.base import Plugin_Base
    from COMTool.i18n import _
    from COMTool.conn import  ConnectionStatus

class Plugin(Plugin_Base):
    id = "myplugin"
    name = _("my plugin")
    updateSignal = pyqtSignal(str, bytes)

    def onConnChanged(self, status:ConnectionStatus, msg:str):
        print("-- connection changed: {}, msg: {}".format(status, msg))

        if status == ConnectionStatus.CONNECTED:
            self.frame_data = []
            self.frame_num = 0
            self.packet_num = 0

            self.fps_start_tm = 0
            self.fps_num = 0
            self.fps = 0

            self.curr_image = b''

    def onWidgetMain(self, parent):
        '''
            main widget, just return a QWidget object
        '''
        self.widget = QWidget()
        layout = QVBoxLayout()
        
        self.label = QLabel();
        self.label.setMinimumWidth(100)

        layout.addWidget(self.label)

        self.widget.setLayout(layout)

        self.updateSignal.connect(self.updateUI)

        return self.widget


    def updateUI(self, dataType, data : bytes):
        '''
            UI thread
        '''

        if dataType == "jpeg" or dataType == "update_fps":
            if data:
                qimage = QImage.fromData(data);

                painter = QPainter(qimage)
                font = QFont('arial.ttf', 16)
                # font.setPointSize(16)
                painter.setFont(font)
                painter.setPen(QColor(255, 0, 0))

                text = "fps:" + str(int(self.fps))
                painter.drawText(0, 16, text)
                painter.end()  # 结束绘制操作

                qpixmap = QPixmap.fromImage(qimage)
                qpixmap = qpixmap.scaled(self.widget.size(), Qt.KeepAspectRatio)
                self.label.setPixmap(qpixmap);
                self.label.show();
                self.curr_image = data

    def onReceived(self, data : bytes):
        '''
            call in receive thread, not UI thread
        '''
        super().onReceived(data)
        if len(data) > 4:
            # 解析包头
            header = data[0:4]
            (header_flag, packet_frame_num, packet_num, last_packet_flag) = struct.unpack('BBBB', header)
            
            # 判断包头标志
            if header_flag != 0xAA:
                return
        
            if self.frame_num != packet_frame_num:
                self.frame_num = packet_frame_num
                self.packet_num = 0
                self.frame_data = []
            
            # 将包添加到列表中
            self.frame_data.append((packet_num, data[4:]))
            
            # 如果是最后一个包，则组合成完整的JPEG图片
            if last_packet_flag:
                self.packet_num = packet_num

            # 判断是否所有的包都接收到了
            if self.packet_num != 0 and len(self.frame_data) == self.packet_num + 1:
                # 按照包序号排序
                sorted_packets = sorted(self.frame_data, key=lambda x:x[0])
                
                # 组合数据
                data = b''
                for packet in sorted_packets:
                    data += packet[1]
                
                self.updateSignal.emit("jpeg", data)

                self.fps_num += 1 
                self.packet_num = 0
                self.frame_data = []

        now = int(time.time()*1000)
        if now - self.fps_start_tm > 1000:
            self.fps = round((self.fps_num)/(now - self.fps_start_tm)*1000, 2)
            self.fps_start_tm = now
            self.fps_num = 0 
            self.updateSignal.emit("update_fps", self.curr_image)