import daemon
import time
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import smtplib
import MySQLdb
from config import *

class AlarmFrame:
	def __init__(self, row):
		self.frameId = row[0]
		self.frameDate = row[1]
		self.score = row[2]
		self.eventName = row[3]
		self.eventDate = row[4]
		self.monitorName = row[5]
		self.eventId = row[7]

	monitorName = ""
	eventDate = None
	frameDate = None
	frameId = None
	score = None
	eventId = None
	eventName = None

def open_db():
	db = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASSWD, db=DB_NAME)
	return db

def get_todo(db):
	c = db.cursor()
	query = """select f.frameid, f.timestamp as frame_timestamp, f.score, 
        e.name as event_name, e.starttime, m.name as monitor_name, 
        au.upload_timestamp, f.eventid 
        from Frames f 
        join Events e on f.eventid = e.id 
        join Monitors m on e.monitorid = m.id
        left join alarm_uploaded au on (au.frameid = f.frameid and au.eventid = f.eventid) 
        where f.type = 'Alarm' 
		  AND f.score > {minimum_score} 
		  and upload_timestamp is null
		  and f.timestamp > '{ignore_before}' """
	query = query.format(minimum_score=MIN_SCORE, ignore_before=IGNORE_BEFORE)

		  
	if len(MONITOR_NAMES) > 0:
		query += "AND m.name IN ('"
		query += "','".join(MONITOR_NAMES)
		query += "') "
	
	query += "ORDER BY f.eventid, f.frameid ASC limit 0,{batch_size} "
	query = query.format(batch_size=BATCH_SIZE)

	print query
	numrows = c.execute(query)
	if numrows > 0:
		return c.fetchall()
	else:
		return None

def get_path(alarmFrame):
	path = ZM_PATH
	path += alarmFrame.monitorName + '/'
	path += alarmFrame.eventDate.strftime('%y') + '/'
	path += alarmFrame.eventDate.strftime('%m') + '/'
	path += alarmFrame.eventDate.strftime('%d') + '/'
	path += alarmFrame.eventDate.strftime('%H') + '/'
	path += alarmFrame.eventDate.strftime('%M') + '/'
	path += alarmFrame.eventDate.strftime('%S') + '/'
	path += format(alarmFrame.frameId, '03') + '-capture.jpg'
	
	return path

def make_email():
	msg = MIMEMultipart()
	msg['Subject'] = EMAIL_SUBJECT
	msg['From'] = FROM_EMAIL
	msg['To'] = TO_EMAIL
	return msg

def add_frame(msg, alarmFrame):
	path = get_path(alarmFrame)
	fp = open(path, 'rb')
	img = MIMEImage(fp.read())
	fp.close()
	msg.attach(img)

	return msg

def get_server():
	server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
	server.starttls()
	if len(SMTP_LOGIN) > 0 and len(SMTP_PASSWORD) > 0:
		server.login(SMTP_LOGIN, SMTP_PASSWORD)
	return server

def send_email(msg):
	server = get_server()
	server.sendmail(FROM_EMAIL,TO_EMAIL,msg.as_string()) 
	server.quit()

def update_db(db, alarmFrame):
	c = db.cursor()
	c.execute('INSERT INTO alarm_uploaded (frameid,upload_timestamp,eventid)  VALUES (%s, NOW(), %s)', (alarmFrame.frameId, alarmFrame.eventId))
	db.commit()
	

def process_new(db):
	rows = get_todo(db)
	if rows:
		msg = make_email()
		for row in rows:
			alarmFrame = AlarmFrame(row)
			add_frame(msg, alarmFrame)
			#print alarmFrame.monitorName + ' - ' + str(alarmFrame.eventDate)
		send_email(msg)

		for row in rows:
			alarmFrame = AlarmFrame(row)
			update_db(db, alarmFrame)
		return True
	return False

def main():
	with daemon.DaemonContext():
		db = open_db()
		while True:
			print "Searching..."
			found = process_new(db)
			if found == False:
				print "Sleeping..."
				time.sleep(WAIT_TIME)

main()
