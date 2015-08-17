# -*- coding: utf-8 -*-
#
# -----------------------------------------------------------------------------------
# Copyright (c) Microsoft Open Technologies (Shanghai) Co. Ltd.  All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#  
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# -----------------------------------------------------------------------------------

# "javascript" section for javascript. see @app.route('/config.js') in app/views.py

# oauth constants
HOSTNAME = "http://open-hackathon-dev.chinacloudapp.cn"  # host name of the UI site
QQ_OAUTH_STATE = "openhackathon"  # todo state should be constant. Actually it should be unguessable to prevent CSFA
HACKATHON_API_ENDPOINT = "http://open-hackathon-dev.chinacloudapp.cn:15000"

GITHUB_CLIENT_ID = "b8e407813350f26bf537"
GITHUB_CLIENT_SECRET = "daa78ae27e13c9f5b4a884bd774cadf2f75a199f"

QQ_CLIENT_ID = "101200890"
QQ_CLIENT_SECRET = "88ad67bd4521c4cc47136854781cb9b5"
QQ_META_CONTENT = "274307566465013314076545663016134754100636"

# gitcafe domain:  gcas.dgz.sh/gcs.dgz.sh for Staging, api.gitcafe.com/gitcafe.com for Production
GITCAFE_CLIENT_ID = "1c33ecdf4dd0826325f60a92e91834522b1cdf47a7f90bdaa79f0526fdc48727"
GITCAFE_CLIENT_SECRET = "80b63609000b20c1260df28081c08712617648e1b528086bbb089f0af4614509"

WEIBO_CLIENT_ID = "479757037"
WEIBO_CLIENT_SECRET = "efc5e75ff8891be37d90b4eaec5c02de"
WEIBO_META_CONTENT = "ae884e09bc02b700"

LIVE_CLIENT_ID = "000000004414E0A6"
LIVE_CLIENT_SECRET = "b4mkfVqjtwHY2wJh0T4tj74lxM5LgAT2"

Config = {
    "environment": "local",
    "app": {
        "secret_key": "secret_key"
    },
    "mysql": {
        "connection": 'mysql://%s:%s@%s/%s' % ('hackathon', 'hackathon', 'localhost', 'hackathon')
    },
    "login": {
        "github": {
            "access_token_url": 'https://github.com/login/oauth/access_token?client_id=%s&client_secret=%s&redirect_uri=%s/github&code=' % (
                GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, HOSTNAME),
            "user_info_url": 'https://api.github.com/user?access_token=',
            "emails_info_url": 'https://api.github.com/user/emails?access_token='
        },
        "qq": {
            "meta_content": QQ_META_CONTENT,
            "access_token_url": 'https://graph.qq.com/oauth2.0/token?grant_type=authorization_code&client_id=%s&client_secret=%s&redirect_uri=%s/qq&code=' % (
                QQ_CLIENT_ID, QQ_CLIENT_SECRET, HOSTNAME),
            "openid_url": 'https://graph.qq.com/oauth2.0/me?access_token=',
            "user_info_url": 'https://graph.qq.com/user/get_user_info?access_token=%s&oauth_consumer_key=%s&openid=%s'
        },
        "gitcafe": {
            "access_token_url": 'https://gcas.dgz.sh/oauth/token?client_id=%s&client_secret=%s&redirect_uri=%s/gitcafe&grant_type=authorization_code&code=' % (
                GITCAFE_CLIENT_ID, GITCAFE_CLIENT_SECRET, HOSTNAME)
        },
        "weibo": {
            "meta_content": WEIBO_META_CONTENT,
            "user_info_url": 'https://api.weibo.com/2/users/show.json?access_token=',
            "email_info_url": 'https://api.weibo.com/2/account/profile/email.json?access_token=',
            "access_token_url": 'https://api.weibo.com/oauth2/access_token?client_id=%s&client_secret=%s&grant_type=authorization_code&redirect_uri=%s/weibo&code=' % (
                WEIBO_CLIENT_ID, WEIBO_CLIENT_SECRET, HOSTNAME)
        },
        "live": {
            "client_id": LIVE_CLIENT_ID,
            "client_secret": LIVE_CLIENT_SECRET,
            "redirect_uri": '%s/live' % HOSTNAME,
            "access_token_url": 'https://login.live.com/oauth20_token.srf',
            "user_info_url": 'https://apis.live.net/v5.0/me?access_token='
        },
        "provider_enabled": ["github", "qq", "live"],
        "session_minutes": 60,
        "token_expiration_minutes": 60 * 24
    },
    "hackathon-api": {
        "endpoint": HACKATHON_API_ENDPOINT
    },
    "javascript": {
        "github": {
            "authorize_url": "https://github.com/login/oauth/authorize?client_id=%s&redirect_uri=%s/github&scope=user" % (
                GITHUB_CLIENT_ID, HOSTNAME)
        },
        "weibo": {
            "authorize_url": "https://api.weibo.com/oauth2/authorize?client_id=%s&redirect_uri=%s/weibo&scope=all" % (
                WEIBO_CLIENT_ID, HOSTNAME)
        },
        "qq": {
            "authorize_url": "https://graph.qq.com/oauth2.0/authorize?client_id=%s&redirect_uri=%s/qq&scope=get_user_info&state=%s&response_type=code" % (
                QQ_CLIENT_ID, HOSTNAME, QQ_OAUTH_STATE)
        },
        "gitcafe": {
            "authorize_url": "https://gcs.dgz.sh/oauth/authorize?response_type=code&client_id=%s&redirect_uri=%s/gitcafe&scope=public" % (
                GITCAFE_CLIENT_ID, HOSTNAME)
        },
        "live": {
            "authorize_url": 'https://login.live.com/oauth20_authorize.srf?client_id=%s&scope=wl.basic+,wl.emails&response_type=code&redirect_uri=%s/live' % (
                LIVE_CLIENT_ID, HOSTNAME)
        },
        "hackathon": {
            "name": "open-xml-sdk",
            "endpoint": HACKATHON_API_ENDPOINT
        },
        "apiconfig": {
            "proxy": HACKATHON_API_ENDPOINT,
            "api": {
                "admin": {
                    "hackathon": {
                        "": ["get", "post", "put"],
                        "checkname": ["get"],
                        "list": ["get"],
                        "administrator": {
                            "": ["put", "post", "delete"],
                            "list": ["get"]
                        },
                        "template": {
                            "": ["post", "delete"],
                            "list": ["get"],
                            "check": ["get"]
                        }
                    },
                    "registration": {
                        "": ["get", "post", "delete", "put"],
                        "list": ["get"]
                    },
                    "azure": {
                        "": ["get", "post", "delete", "put"],
                    },
                    "experiment": {
                        "list": ["get"],
                        "": ["post", "put"]
                    }
                },
                "template": {
                    "": ["get", "post", "delete", "put"],
                    "list": ["get"],
                    "check": ["get"]
                },
                "user": {
                    "": ["get"],
                    "experiment": {
                        "": ["get", "post", "delete", "put"],
                        "list": ["get"]
                    },
                    "registration": {
                        "": ["put", "post", "get"],
                        "checkemail": ["get"],
                        "list": ["get"]
                    },
                    "profile": {
                        "": ["get", "post", "put"]
                    },
                    "team": {
                        "member": ["get"]
                    }
                },
                "hackathon": {
                    "": ["get"],
                    "list": ["get"],
                    "stat": ["get"],
                    "template": ["get"],
                    "team": {
                        "list": ["get"]
                    },
                    "registration": {
                        "list": ["get"]
                    }
                },
                "team": {
                    "": ["get", "post"],
                    "user": ["get"],
                    "list": ["get"],
                    "leader": ["put"],
                    "member": {
                        "": ["post", "put"],
                        "list": ["get"]
                    }
                }
            }
        }
    }

}
