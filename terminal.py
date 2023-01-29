'''
    @brief This is an example plugin, can receive and send data
    @author
    @date
    @license LGPL-3.0
'''
import os
import re
import subprocess
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import *
import pyte

try:
    from plugins.base import Plugin_Base
    from conn import ConnectionStatus
    from i18n import _
except ImportError:
    from COMTool.plugins.base import Plugin_Base
    from COMTool.i18n import _
    from COMTool.conn import  ConnectionStatus

class Terminal_TextEdit(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet("background:black")
        self.setReadOnly(True);

    # def keyPressEvent(self, event):
    #     self.setReadOnly(False);
    #     super().keyPressEvent(event);
    #     self.setReadOnly(True);

class Plugin(Plugin_Base):
    id = "myplugin"
    name = _("my plugin")
    updateSignal = pyqtSignal(str, list)
    lastColor = None
    lastBg = None
    last_remain = b''

    def onInit(self, config):
        '''
            init params, DO NOT take too long time in this func
            @config dict type, just change this var's content,
                               when program exit, this config will be auto save to config file
        '''
        self.config = config
        default = {
            "version": 1,
            "elfFile": "hello.elf",
            "toolchain": "/xtensa-esp32-elf-addr2line",
            "reFilter": "0x4[0-9a-f]{7}",
            "cmdArg": "-pfiaC -e",
        }
        for k in default:
            if not k in self.config:
                self.config[k] = default[k]

    def onConnChanged(self, status:ConnectionStatus, msg:str):
        print("-- connection changed: {}, msg: {}".format(status, msg))

    def onWidgetMain(self, parent):
        '''
            main widget, just return a QWidget object
        '''
        self.widget = QWidget()
        layout = QVBoxLayout()
        # receive widget
        self.receiveArea = Terminal_TextEdit()
        font = QFont('Menlo,Consolas,Bitstream Vera Sans Mono,Courier New,monospace, Microsoft YaHei', 10)
        self.receiveArea.setFont(font)

        # add widgets
        layout.addWidget(self.receiveArea)
        self.widget.setLayout(layout)

        self.screen = pyte.HistoryScreen(60, 20, history=9999, ratio = 0.05)
        self.screen.set_mode(pyte.modes.LNM)
        self.stream = pyte.ByteStream(self.screen)

        self.updateSignal.connect(self.updateUI)
        return self.widget
    
    def onWidgetSettings(self, parent):
        root = QWidget()
        rootLayout = QVBoxLayout()
        rootLayout.setContentsMargins(0,0,0,0)
        root.setLayout(rootLayout)

        setingGroup = QGroupBox(_("add2line"))
        layout = QGridLayout()
        setingGroup.setLayout(layout)

        self.elfFile = QLineEdit(self.config["elfFile"])
        self.elfFileSelect = QPushButton('...')

        self.toolchain = QLineEdit(self.config["toolchain"])
        self.toolchainSelect = QPushButton('...')

        self.reFilter = QLineEdit(self.config["reFilter"])

        self.cmdArg = QLineEdit(self.config["cmdArg"])
        layout.addWidget(self.elfFile,0,0,1,1)
        layout.addWidget(self.elfFileSelect,0,1,1,1)
        layout.addWidget(self.toolchain,1,0,1,1)
        layout.addWidget(self.toolchainSelect,1,1,1,1)
        layout.addWidget(self.reFilter,2,0,1,2)
        layout.addWidget(self.cmdArg,3,0,1,2)

        rootLayout.addWidget(setingGroup)

        self.elfFileSelect.clicked.connect(self.elfFileButtonHandle)
        self.toolchainSelect.clicked.connect(self.toolchainButtonHandle)
        return root

    def lookup_pc_address(self, pc_addr):  # type: (str) -> None
        cmd = self.config["toolchain"] + ' ' + self.config["cmdArg"] + ' ' + self.config["elfFile"] + ' ' + pc_addr
        try:
            translation = subprocess.check_output(cmd, cwd='.')
            if b'?? ??:0' not in translation and b'??:' not in translation:
                return translation.decode()
        except OSError as e:
            pass
        return None

    def elfFileButtonHandle(self):
        fileName, fileType = QFileDialog.getOpenFileName(None, "elfFile")

        self.config["elfFile"] = fileName
        self.elfFile.setText(self.config["elfFile"])

    def toolchainButtonHandle(self):
        fileName, fileType = QFileDialog.getOpenFileName(None, "toolchain")

        self.config["toolchain"] = fileName
        self.toolchain.setText(self.config["toolchain"])

    def buttonSend(self):
        '''
            UI thread
        '''
        data = self.input.toPlainText()
        if not data:
            # to pop up a warning window
            self.hintSignal.emit("error", _("Error"), _("Input data first please") )
            return
        dataBytes = data.encode(self.configGlobal["encoding"])
        self.send(dataBytes)

    def _getColorByfmt(self, fmt:bytes):
        colors = {
            b"0": None,
            b"30": "#000000",
            b"31": "#f44336",
            b"32": "#4caf50",
            b"33": "#ffa000",
            b"34": "#2196f3",
            b"35": "#e85aad",
            b"36": "#26c6da",
            b"37": "#a1887f",
        }
        bgs = {
            b"0": None,
            b"40": "#000000",
            b"41": "#f44336",
            b"42": "#4caf50",
            b"43": "#ffa000",
            b"44": "#2196f3",
            b"45": "#e85aad",
            b"46": "#26c6da",
            b"47": "#a1887f",
        }
        fmt = fmt[2:-1].split(b";")
        color = colors[b'0']
        bg = bgs[b'0']
        for cmd in fmt:
            if cmd in colors:
                color = colors[cmd]
            if cmd in bgs:
                bg = bgs[cmd]
        return color, bg

    def _texSplitByColor(self, text:bytes):
        remain = b''
        ignoreCodes = [rb'\x1b\[\?.*?h', rb'\x1b\[\?.*?l']
        text = text.replace(b"\x1b[K", b"")
        for code in ignoreCodes:
            colorFmt = re.findall(code, text)
            for fmt in colorFmt:
                text = text.replace(fmt, b"")
        colorFmt = re.findall(rb'\x1b\[.*?m', text)
        if text.endswith(b"\x1b"): # ***\x1b
            text = text[:-1]
            remain = b'\x1b'
        elif text.endswith(b"\x1b["): # ***\x1b[
            text = text[:-2]
            remain = b'\x1b['
        else: # ****\x1b[****, ****\x1b[****;****m
            idx = -2
            idx_remain = -1
            while 1:
                idx = text.find(b"\x1b[", len(text) - 10 + idx + 2) # \x1b[00;00m]
                if idx < 0:
                    break
                remain = text[idx:]
                idx_remain = idx
            if len(remain) > 0:
                match = re.findall(rb'\x1b\[.*?m', remain)  # ****\x1b[****;****m***
                if len(match) > 0: # have full color format
                    remain = b''
                else:
                    text = text[:idx_remain]
        plaintext = text
        for fmt in colorFmt:
            plaintext = plaintext.replace(fmt, b"")
        colorStrs = []
        if colorFmt:
            p = 0
            for fmt in colorFmt:
                idx = text[p:].index(fmt)
                if idx != 0:
                    colorStrs.append([self.lastColor, self.lastBg, text[p:p+idx]])
                    p += idx
                self.lastColor, self.lastBg = self._getColorByfmt(fmt)
                p += len(fmt)
            colorStrs.append([self.lastColor, self.lastBg, text[p:]])
        else:
            colorStrs = [[self.lastColor, self.lastBg, text]]
        return plaintext, colorStrs, remain

    def getColoredText(self, data_bytes, decoding=None):
        plainText, coloredText, remain = self._texSplitByColor(data_bytes)
        if decoding:
            plainText = plainText.decode(encoding=decoding, errors="ignore")
            decodedColoredText = []
            for color, bg, text in coloredText:
                decodedColoredText.append([color, bg, text.decode(encoding=decoding, errors="ignore")])
            coloredText = decodedColoredText
        return plainText, coloredText, remain

    def updateUI(self, dataType, coloredText):
        '''
            UI thread
        '''
        if dataType == "receive":
            for color, bg, text in coloredText:
                # f = re.finditer(".*\n", text)
                for m in re.finditer("(.*\n)|(.*$)", text):
                    line = m.group()
                    if line:
                        cursor = self.receiveArea.textCursor()
                        cursor.movePosition(QTextCursor.End) # 还可以有别的位置

                        self.receiveArea.setTextCursor(cursor)
                        
                        format = cursor.charFormat()
                        if color:
                            format.setForeground(QColor(color))
                            cursor.setCharFormat(format)
                        else:
                            format.setForeground(QColor("#ffffff"))
                            cursor.setCharFormat(format)
                        cursor.insertText(line)

                        for m in re.finditer(self.config["reFilter"], line):
                            translation = self.lookup_pc_address(m.group())
                            if translation:
                                format.setForeground(QColor("#ffa000"))
                                cursor.setCharFormat(format)

                                cursor.insertText("\r\n" + translation + "\r\n")
               

    def onReceived(self, data : bytes):
        '''
            call in receive thread, not UI thread
        '''
        super().onReceived(self.last_remain+data)
        
        plainText, coloredText, remain = self.getColoredText(self.last_remain+data, self.configGlobal["encoding"])

        self.last_remain = remain

        self.updateSignal.emit("receive", coloredText)

        # DO NOT set seld.receiveBox here for all UI operation should be in UI thread,
        # instead, set self.receiveBox in UI thread, we can use signal to send data to UI thread
