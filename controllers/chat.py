# coding=utf-8

from __future__ import unicode_literals
import tornado.web
import time,json,re

import record
from record import db
from record import rooms
from record import users
from session import Session

def sysmsg(room,text):
    msg.send_msg(room,'系统消息',text,int(time.time()))

class room(tornado.web.RequestHandler):
    # 检查连接
    def checkconn(self):
        if not self.request.connection.stream.closed():
            return True
    # 获取房间信息
    def get(self,room):
        if not room:
            # 返回所有信息
            ret = rooms.getinfo()
            if not self.checkconn:return
            self.finish(ret)
            return
        if not room in users:
            self.finish('+ERR 100')
            return 
        self.finish(rooms[room])
    # 进入/离开房间
    def post(self,room):
        _cmd  = self.get_argument('cmd')
        if _cmd == 'ENTER':
            uuid = self.get_secure_cookie('alice')
            if not uuid:return
            session = Session(uuid)
            user = session['user']
            room = session['room'] = self.get_argument('room')
            if not room in users:
                users[room] = dict()
                rooms.addroom(room)
            users[room][user] = []
            # 返回前20条聊天记录，时间限制在30分钟内。
            self.finish({'record':record.getchatrecord(room,20)})
            sysmsg(room,'用户 '+user+' 进入房间')
        elif _cmd == 'LEAVE':
            uuid = self.get_secure_cookie('alice')
            if not uuid:return
            session = Session(uuid)
            room = session['room']
            user = session['user']
            if user and room and user in users[room]:
                del users[room][user]
                sysmsg(room,'用户 '+user+' 离开房间')
                session['room'] = None

# 收发消息
class msg(tornado.web.RequestHandler):
    callbacks = {}

    @tornado.web.asynchronous
    def get(self):
        # 初始化 session
        uuid = self.get_secure_cookie('alice')
        if not uuid:return
        session = Session(uuid)

        # 检查房间是否存在
        room = session['room']
        if not room in self.callbacks:
            self.callbacks[room] = list()
        # 添加至回调列表
        self.callbacks[room].append([session['user'],self.on_new_msg])

    def post(self):
        # 初始化 session
        uuid = self.get_secure_cookie('alice')
        if not uuid:return
        session = Session(uuid)

        # 发送消息
        _room = session['room']
        _user = session['user']
        _msg  = self.get_argument('msg')
        _time = int(time.time())
        self.send_msg(_room,_user,_msg,_time)

    @staticmethod
    def send_msg(room,usr,msgtext,time):
        db.query('insert into chat(room,user,time,msg) values(?,?,?,?)',(room,usr,time,msgtext))
        rooms[room] = {'user':usr,'msg':msgtext,'time':time}
        db.commit()
        if not room in msg.callbacks:return
        for callback in msg.callbacks[room]:
            callback[1](usr,msgtext,time,room,callback[0])
        msg.callbacks[room] = list()

    def on_new_msg(self,usr,msg,time,room=None,sendto=None):
        if self.request.connection.stream.closed():
            if sendto and room and sendto in users[room]:
                del users[room][sendto]
                sysmsg(room,'用户 '+sendto+' 离开房间')
            return
        if sendto != usr:
            self.finish({"user":usr,"msg":msg,"time":time})

