import datetime, xmlrpclib
import mimetypes
import os

wp_url = "http://localhost/wordpress/xmlrpc.php"
wp_username = "admin"
wp_password = "longitude"
wp_blogid = ""

status_draft = 0
status_published = 1

server = xmlrpclib.ServerProxy(wp_url)

title = "New Wordpress Thread Title"
content = "Body with lots of content"
date_created = xmlrpclib.DateTime(datetime.datetime.strptime("2011-07-14 02:00", "%Y-%m-%d %H:%M"))
categories = ["headerimage"]
tags = ["sometag", "othertag"]
data = {'title': title, 'description': content, 'dateCreated': date_created, 'categories': categories, 'mt_keywords': tags}

post_id = server.metaWeblog.newPost(wp_blogid, wp_username, wp_password, data, status_published)
print post_id
mediaFileName = '/var/www/wp-headers/new/Bolton Smiley JPG.jpg'
f = file(mediaFileName, 'rb')
mediaBits = f.read()
f.close()

print os.path.basename(mediaFileName)

imageData = {'name' : os.path.basename(mediaFileName),
             'bits' : xmlrpclib.Binary(mediaBits),
            'type' : mimetypes.guess_type(mediaFileName)[0]}

testing = server.metaWeblog.newMediaObject(post_id, wp_username, wp_password, imageData)
print testing['url']