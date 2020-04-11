# -*- coding: utf-8 -*-

env_local = {
    'deploy_dir': 'N/A',
    '_env': {
        'FLASK_ENV': 'development',
        'FLASK_RUN_PORT': 5001,
        'FLASK_RUN_WITH_THREADS': 1,
    },
    'uwsgi_ini': {
        'socket': '127.0.0.1:5000',
        'daemonize': False,
    },
    'config_json': {
        'FLASK': {
            'SQLALCHEMY_DATABASE_URI': 'mysql+pymysql://zrong:123456@127.0.0.1/pyape_local',
        },
        'PATH': {
            'STATIC_URL_PATH': '',
            'modules': {
                'cf': '/cf',
            }
        },
        'REGIONALS': [
            {
                'name': '测试服1000',
                'index': 1,
                # 服务端依赖其作为校验，与 regional 的值相同
                'r': 1000,
            },
        ],
    },
}
