#====================================
# 使用 Gunicorn 部署 pyape 实例时候的配置文件
# 2020-05-17
# author: zrong
#====================================
import multiprocessing
import os      

wsgi_app = 'wsgi:sample_app'
proc_name = 'sample'
user = 'app'
group = 'app'
umask = 0
bind = '127.0.0.1:5001'
workers = multiprocessing.cpu_count() * 2 + 1
daemon = True
capture_output = True