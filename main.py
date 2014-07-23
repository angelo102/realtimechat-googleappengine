import jinja2
import os
import webapp2
import urllib
import datetime

from google.appengine.api import app_identity
from google.appengine.api import channel
from google.appengine.api import users

from google.appengine.ext import ndb

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


#model for connected clients
class ChannelKey(ndb.Model):
  ch_key = ndb.StringProperty()
  token = ndb.StringProperty()

class MessageNDB(ndb.Model):
  user = ndb.StringProperty()
  date = ndb.DateTimeProperty(auto_now_add=True)
  message = ndb.StringProperty()

class Message(webapp2.RequestHandler):
    def post(self):
      #get the client_key from client
      client_key = self.request.get('client_key')
      #get message from client
      message = self.request.get('m')
      if message:
        broadcast_message = client_key + " wrote:   " + message
        #check if client has previously being stored
        ch_key = ChannelKey.query(ChannelKey.ch_key==client_key)
        
        if ch_key.get() is None:
          #send message to own client
          channel.send_message(str(client_key),broadcast_message)
        
        #save message on Message Kind (other name for tables in google app engine)
        nosqlmessage = MessageNDB(user=client_key, message=broadcast_message)
        nosqlmessage.put()
        #send message to all connected clients
        ch_keys = ChannelKey.query().fetch(1000)

        for key in ch_keys:
          channel.send_message(str(key.ch_key),broadcast_message)
          
class OpenedChannel(webapp2.RequestHandler):
    def post(self):
      #get the client_key from client
      client_key = self.request.get('client_key')
   
      if not client_key:
        client_key = users.get_current_user().email()
      
      #save Channel
      new_key = ChannelKey(ch_key=str(client_key))
      new_key.put()

      #retrieve 7 days of messages from datastore
      date1 = datetime.datetime.now() - datetime.timedelta(days=7)
      m_history = MessageNDB.query(MessageNDB.date > date1)
      m_history2 = m_history.order(MessageNDB.date)
      result = m_history2.fetch(1000)
      
      #send data to client
      #Store log messages in one string
      marray = "&log"
      for m in result:
        marray = marray+"&"+str(m.message)
      
      #send via the channel
      channel.send_message(str(client_key), marray)

class ClosedChannel(webapp2.RequestHandler):
  def post(self):
    #get the client_key from client
    client_key = self.request.get('client_key')
    #delete channel key from connected users
    ndb.delete_multi(ChannelKey.query(ChannelKey.ch_key==str(client_key)).fetch(keys_only=True))
   
    
class DeleteMess(webapp2.RequestHandler):
  def post(self):
    ndb.delete_multi(ChannelKey.query().fetch(keys_only=True))
    #ndb.delete_multi(MessageNDB.query().fetch(keys_only=True))

class MainPage(webapp2.RequestHandler):
  def get(self):
    #get user and login
    usr = users.get_current_user()
    if not usr:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Login'
      self.redirect(users.create_login_url(self.request.uri))
    else:
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'

      #get the client key to start a channel
      key = self.request.get('client_key')
      if not key:
        key = usr.email()
      
      #create token to use on channel with client
      token = channel.create_channel(str(key))
   
      #send template values
      template_values = {'user': usr,
                         'token': token,
                         'client_key': key,
                         'url': url,
                         'url_linktext': url_linktext,
                        }
      template = JINJA_ENVIRONMENT.get_template('index.html')
      self.response.write(template.render(template_values))

application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/message', Message),
    ('/del', DeleteMess),
    ('/opened', OpenedChannel),
    ('/closed', ClosedChannel),
], debug=True)