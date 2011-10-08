#! /usr/bin/python

import sys, os, shutil
import random
import subprocess
import Image
import datetime, time
import xmlrpclib
import mimetypes
import optparse

x = """
Description:
============
This class handles some functionality for working with the header in wordpress.
It currently changes the header image in a wordpress installation when called 
from the command line (say, by a cron). If text information is provided along
with a new image, the title, content and a thumbnail are blogged to encourage
discussion and analysis.

The code requires a directory that will store the user-dropped images. Here are
the following important directories:

1) /var/www/wp-headers
-------------------
New top level web directory, currently wide open.

2) /var/www/wp-headers/new
-----------------------
The directory into which people dump images (and text). The code will randomly
select a new image from this directory when called. If it has no content (ie.
there are no new images), an image will be selected at random from the ../old 
directory.

If a .txt file of the same name as the image name (say foo.jpg and foo.txt) is
found in this directory (with a specific format - below), this information is 
posted to a new blog thread (within a "headers" category). The image itself
is also thumbnailed and inserted into the blog so there is a record of what the
text and discussion is referencing.

3) /var/www/wp-headers/old
-----------------------
Stores images once they've been used as the header. Does not store the textfiles
as they've been blogged. Also acts as a back up (recycle) if no new images are
placed in the /new directory. If there's nothing in here - someone remove all - 
then the current one will remain. 

4) /var/www/wordpress/wp-content/themes/twentyten/images/headers
----------------------------------------------------------------
A wordpress folder. The place wordpress stores all of its header images. 
Because of the way wp is set up (or my stupidity), I'm just writing over one 
of it's existing files. This allows me to point it at that file in the wp 
admin interface. This file will need to have write access to the cron of the user.

5) /var/www/wp-uploads/localhost/
---------------------------------
The directory structure below this is ....localhost/YEAR/month/ (/localhost/2011/07/<files>
This is where wordpress will store user uploaded media, such as the image thumbnail.
Its also the URL that XMLRPC will return to you after you've uploaded the
file - that's how I insert the image thumbnail. Except its not. See "Problems" 
below...


Text File Format:
------------
title: This is the text that will go in the title field.
content: This goes into the content of the post.
tags: A place for semi-colon delimeted tags for the post.

Improvements:
=============
Come up with a better method for text input (if its of any use)
Come up with a better tag delimeter method that ;. Or more options (space, comma, etc)
Add a category field to the textfile reader to allow posting to different categories.
Maybe keep the text file for prosperity?

Problems:
=========
The URL returned by the XMLRPC command: newMediaObject gives an incorrect URL
It returns: http://localhost/wp-uploads/2011/07/fern_thumb.jpg
Correct is: http://localhost/wp-uploads/localhost/2011/07/fern_thumb.jpg
May have to wait and see if this is correct under a proper webserver...?

I suspect this is riddled with gaps to be exploited by your village hacker. 
Especially the uploading of unchecked binary and inserting that...?

R.Brantingham July 2011.

"""

class newHeader(object):
    
    def __init__(self, verbose, oldDir, newDir, headerDir, headerFile, wpUrl, wpUser, wpPswd):
        ''' Build some useful attributes/variables. '''
        self.oldDir     = oldDir
        self.newDir     = newDir
        self.headerDir  = headerDir
        self.headerFile = headerFile
        self.wpUrl      = wpUrl
        self.wpUser     = wpUser
        self.wpPswd     = wpPswd
        self.verbose    = verbose
        self.ferror     = open('/home/robrant/code/wordpress/logging_testing.txt', 'a')
#------------------------------------------------------------------------------#

    def run(self):
    
        # Check for the existence of all 3 directories. 
        self.checkDirectories()
        # Try touch test on wordpress formal header directory (3 above).
        self.touchToHeader()
            
        # Get content of new_dir into candidate list - all files, no filter
        newContent = self.getDirContents(self.newDir)
        
        # If there are images in the 'new' folder, work with those.
        if len(newContent) != 0:

            # First reformat any images in there that aren't PNGs
            self.reformatImage(newContent, squidge=None)
            
            # Get the new directory Content list - only jpgs this time
            newContent = self.getDirContents(self.newDir, 'jpg')
            
            # Now select a winning image
            winner = self.pickFile(self.newDir, newContent)
            newIm = True
            
            # Is there text to go with it? If so, post it and a thumbnail of image
            self.buildThread(winner)
            
            # Copy the  file in to the wordpress directory
            self.copyWinner(winner)
            self.moveWinner(winner)
            
        # else - work with the jpgs that have already been used (stored in 'old')
        else:
            oldContent = self.getDirContents(self.oldDir, 'jpg')

            if len(oldContent) != 0:
                winner = self.pickFile(self.oldDir, oldContent)
                self.copyWinner(winner)
            else:
                self.errors("No images in /new or /old directories. Leaving current image")
                
#------------------------------------------------------------------------------#

    def checkDirectories(self):
        ''' Check the 3 important directories. Exit if they don't exist.  '''

        # Check the old images directory
        if not os.path.exists(self.oldDir)==True:
            self.errors('/old directory does not exist.')
            
        # Check the new images directory
        if not os.path.exists(self.newDir)==True:
            self.errors('/new image directory does not exist.')

        # Check the Wordpress formal header image directory
        if not os.path.exists(self.headerDir)==True:
            self.errors('Header Directory does not exist.')


#------------------------------------------------------------------------------#

    def touchToHeader(self):
        ''' Attempts to touch a file into the wordpress header directory.
            Attempts to delete the touched file. Exits if it can't do either.'''

        testLoc = self.headerDir+'test'
        args = ['touch',testLoc]
        process = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        x = process.communicate()
        if len(x[1]) > 0:
            self.errors('Cannot write to the header directory.')
        else:
            args = ['rm',testLoc]
            process = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            x = process.communicate()            
            if len(x[1]) > 0:
                self.errors('Cannot delete from header directory.')

#------------------------------------------------------------------------------#

    def getDirContents(self, dir, suffix=None, contents = []):
        ''' Generic retrieval of a list of files in the 'dir' folder. 
            Exits if it fails to get the directory content. Returns a list.
            If a file type is provided, it only lists that file type in contents'''
        
        try:
            # Return everything
            if suffix==None:
                contents = os.listdir(dir)
            
            # If suffix is present, return based on suffix filter
            else: 
                for file in os.listdir(dir):
                    if file[-3:] == suffix:
                        contents.append(file)
            return contents
        
        except:
            self.errors('Failed to retrieve contents for %s' %(dir))
            
#------------------------------------------------------------------------------#

    def reformatImage(self, content, squidge=None, xOut=940, yOut=198):
        ''' Resizes EVERY image in the 'new' images folder and converts it
            to a jpg ready for selection. Also modifies the image using 1 of 
            2 methods. If squidge!=None, it just resizes the entire image into
            the size. If squidge==None, it takes the centre of the image and 
            inputs that. It'll handle images that are smaller than the out size.
            xOut and yOut are the required dimensions of the output image.'''
        
        # Loop each image in the 'new' folder and resize and convert to a jpg.
        for file in content:

            if file[-4:] == '.png':
                fName = self.newDir + file[:-4]
                try:
                    im = Image.open(fName+'.png')
                except:
                    continue
                
            # If its a jpg or JPG
            elif file[-4:].lower() =='.jpg':
                fName = self.newDir + file[:-4]
                try: im = Image.open(fName+file[-4:])
                except: continue
            elif file[-5:].lower() =='.jpeg':
                fName = self.newDir + file[:-5]
                try: im = Image.open(fName+file[-5:])
                except: continue
            else:
                continue
            
            x,y = im.size
            
            # Option to resize it (squidge it)
            if squidge:
                if (x!=xOut or y!=yOut):
                    out = im.resize((xOut, yOut))
                else: continue
            
            # Crop out the centre of the image. 
            elif not squidge:
                if x > xOut:
                    left, right = (x/2)-(xOut/2), (x/2)+(xOut/2)
                else: left, right = 0, x
                if y > yOut:
                    upper,lower = (y/2)-(yOut/2),  (y/2)+(yOut/2)
                else: upper, lower = 0, y

                out = im.crop((left, upper, right, lower))
            else: continue
            
            # Having reformatted the png, remove it.
            if file[-4:].lower() == '.png' or file[-5:].lower() == '.jpeg':
                os.remove(self.newDir + file)
            out.convert('RGB').save(fName+'.jpg', "JPEG")

#------------------------------------------------------------------------------#

    def pickFile(self, dir, content):
        ''' Randomly picks the new file for the wordpress header image. '''

        numFiles = len(content)
        if numFiles==1:
            x = 0
        else:
            x = random.randint(0, numFiles-1)
        winner = dir + content[x]
        
        return winner
#------------------------------------------------------------------------------#

    def copyWinner(self, src):
        ''' Copies the selected file into the directory, to be the new header image.'''

        dst = self.headerDir + self.headerFile
        
        # Copy the file
        try:
            shutil.copyfile(src, dst)
        except IOError:
            self.errors("Failed to copy '%s' to destination '%s'.") %(src, dst)
        
        # Check for modification date to make sure it copied.
        modTime = os.path.getmtime(dst)
        t = datetime.datetime.now()
        now = time.mktime(t.timetuple())
        if abs(now - modTime) < 60:
            print "successfully updated the file."
        else:
            self.errors("The image update probably didn't work. Check it")

#------------------------------------------------------------------------------#

    def moveWinner(self, src):
        ''' Moves the winning file into the  old directory.'''
        
        fName = src.split('/')[-1]
        dst = self.oldDir + fName

        # Copy the file
        try:
            shutil.move(src, dst)
        except IOError:
            self.errors("Failed to move selected file '%s' to destination '%s'.") %(src, dst)


#------------------------------------------------------------------------------#

    def buildThread(self, newImage):
        ''' Checks for a textfile of the same name, Opens the text file, 
            Creates a thumbnail of the associated image, Posts the text. 
            Submits the thumbnail at the top of the blog.'''
        
        textFile = os.path.basename(newImage)[:-4] + '.txt'
        f = None
        # Check for textfile of the same name
        for file in os.listdir(self.newDir):
            if file == textFile:
                f = open(self.newDir + file, 'r')
            else: continue

        # If no textfile was found, return.
        if not f: return None
        else:
            title   = "New Header image: %s" %(textFile[-4:])
            content = "Attempted to blog about it, but with no content or bad txt."
            tags    = "bad;upload;header;image"
            cats    = "header;image"

        # Read in the textfile content
        for line in f.readlines():
            
            # Blog title
            if line.lower().find('title') != -1:
                title = line.split(':')[1]

            # Blog content - a description of the image
            if line.lower().find('content') != -1:
                content = line.split(':')[1]
            
            # Semi-colon, comma or space delimited values
            if line.lower().find('tags') != -1:
                tags = self.splitContent(line)

            # Semi-colon, comma or space delimited values
            if line.lower().find('categories') != -1:
                cats = self.splitContent(line)
                
        # Build a thumbnail and upload it
        try:
        
            im = Image.open(newImage)
            im2 = im.resize((345, 49))
            imName = self.oldDir + textFile[:-4]+'_thumb.jpg'
            im2.save(imName, "JPEG")
        except:
            content += " It was not possible to upload a thumbnail of this image."
        
        # Get URL of image. This is problematic - see top of script.
        uploadedImUrl = self.uploadImage(imName)
        
        # Now delete the thumbnail so that it doesn't get picked up again)
        os.remove(imName)
        
        # Format as html
        imgRef = '<img src="%s" alt="Topical Header Image" />' %(uploadedImUrl)
        
        # Insert the URL into the content
        content = imgRef + '\n'*2 + content

        # Publish the lot
        self.publish(title, content, cats, tags)

        # Close and move the file to the old directory. 
        # Removing would be annoying for the author if it errored somewhere.
        f.close()
        shutil.move(self.newDir+textFile, self.oldDir+textFile)

#------------------------------------------------------------------------------#

    def splitContent(self, line):
        ''' Splits multiple values, from a key value pair.   '''
        
        vals = line.split('==')[1]
        vals = vals.rstrip('\n')
        if vals.find(';')   != -1:  vals = vals.split(';')
        elif vals.find(',') != -1:  vals = vals.split(',')
        return vals

#------------------------------------------------------------------------------#

    def publish(self, title, content, categories, tags):
        ''' Handles the posting of a new post text and image thumbnail.   '''

        # Connect and submit the text & thumbnail
        status_draft, status_published = 0, 1
        server = xmlrpclib.ServerProxy(self.wpUrl)
        
        x = datetime.datetime.today().replace(hour=0, minute=0)
        date_created = xmlrpclib.DateTime(x)
        data = {'title': title, 'description': content, 'dateCreated': date_created, 'categories': categories, 'mt_keywords': tags}
        
        wp_blogid = ""
        try:
            post_id = server.metaWeblog.newPost(wp_blogid, self.wpUser, self.wpPswd, data, status_published)
        except:
            self.errors("Failed to post a blog entry associated with image %s" %(title))

#------------------------------------------------------------------------------#

    def uploadImage(self, mediaFileName):
        ''' Taking the full path of the image, uploads the image to wordpress.
            Gets back the url of the uploaded image for putting into the post.
            Note the localhost problem with the URL returned - its incorrect.'''
        
        server = xmlrpclib.ServerProxy(self.wpUrl)
        # Open the image as binary and read the data
        f = file(mediaFileName, 'rb')
        mediaBits = f.read()
        f.close()
        
        # Build a structure/dict to be sent
        imageData = {'name' : os.path.basename(mediaFileName),
                     'bits' : xmlrpclib.Binary(mediaBits),
                     'type' : mimetypes.guess_type(mediaFileName)[0]}
        
        # Submit/upload the  image and get back the URL of the upload
        response = server.metaWeblog.newMediaObject("", self.wpUser, self.wpPswd, imageData)
        imageUrl = response['url']
        url = imageUrl.split('/')
        
        #***** This is where I deal with the localhost error? ***** 
        if 'localhost' in url:
            url = "%s//%s/%s/localhost/%s/%s/%s" %(url[0],url[2],url[3],url[4],url[5],url[6])
        #***** This is where I deal with the localhost error? ***** 
        
        return url

#------------------------------------------------------------------------------#

    def errors(self, errorMessage):
        ''' Prints out any errors and exits python.'''
        if self.verbose == True:
            err = "ERROR: %s. Script Exiting. " %(errorMessage)
            now = datetime.datetime.now()
            self.ferror.write('%s, %s, \n' %(now, err))
        self.ferror.close()
        sys.exit()

#------------------------------------------------------------------------------#

def main():
    
    helpScript = x  # x is the ridiculously long description at the top
    helpVerb = "Option for printing the errors. Else it will fail silently. "
    helpUrl  = "The wordpress XMLRPC url you  want to use. Eg: http://localhost/wordpress/xmlrpc.php"
    helpUser = "The wordpress username to use for blogging text/thumbnails."
    helpPswd = "The wordpress password to use for blogging text/thumbnails."
    
    p = optparse.OptionParser(description=helpScript)
    p.add_option('--verbose',  '-v', action='store_true', help=helpVerb)
    p.add_option('--url',      '-r', dest='url',          help=helpUrl)
    p.add_option('--user',     '-u', dest='user',         help=helpUser)
    p.add_option('--password', '-p', dest='pswd',         help=helpPswd)
    options, arguments = p.parse_args()

    # Parameters for wordpress blogging of new header image
    if options.url:  wp_url      = options.url
    else:            wp_url      = "http://localhost/wordpress/xmlrpc.php"
    if options.user: wp_username = options.user
    else:            wp_username = "admin"
    if options.pswd: wp_password = options.pswd
    else:            wp_password = "longitude"    
    
    # The directory that contains /old and /new folders
    path = '/var/www/wp-headers/'
    # The directory that contains the wordpress headers
    hdPath = '/var/www/wordpress/wp-content/themes/twentyten/images/headers/'
    # this is the wordpress file thats going to get overwritten. Sorry.
    headerFile = 'concave.jpg'
    
    # Kick off the class
    
    nh = newHeader(verbose=options.verbose, oldDir=path+'old/', newDir=path+'new/', \
                    headerDir=hdPath, headerFile = headerFile, \
                    wpUrl=wp_url, wpUser=wp_username, wpPswd=wp_password)
    
    # Run the process function
    nh.run()
    
if __name__ == '__main__':
    main()
    
"""
# THIS SECTION JUST FOR TESTING - OUTSIDE THE COMMAND LINE.

wp_url      = "http://localhost/wordpress/xmlrpc.php"
wp_username = "admin"
wp_password = "longitude"    

# The directory that contains /old and /new folders
path = '/var/www/wp-headers/'
# The directory that contains the wordpress headers
hdPath = '/var/www/wordpress/wp-content/themes/twentyten/images/headers/'
# this is the wordpress file thats going to get overwritten. Sorry concave.
headerFile = 'concave.jpg'

# Kick off the class
nh = newHeader(verbose=True, oldDir=path+'old/', newDir=path+'new/', \
                headerDir=hdPath, headerFile = headerFile, \
                wpUrl=wp_url, wpUser=wp_username, wpPswd=wp_password)

# Run the process function
nh.run()

"""