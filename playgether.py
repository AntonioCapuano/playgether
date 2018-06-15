from flask import Flask, render_template, json, request, redirect, url_for
from flask_pymongo import PyMongo
from flask import jsonify, flash, g, session
from bson.json_util import dumps
from bson import json_util
from datetime import datetime
from email.utils import parseaddr
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
from opencage.geocoder import OpenCageGeocode

app = Flask(__name__)

app.secret_key = "super_secret_key"

app.config['MONGO_DBNAME'] = 'esame_tec_web'
app.config['MONGO_URI'] = 'mongodb://0124001227:Antonio92@ds141720.mlab.com:41720/esame_tec_web'

mongo = PyMongo(app)

key = 'aa06906711c64368a10b589e76f51a86'
geocoder = OpenCageGeocode(key)

@app.route("/")
@app.route("/index")
def index():
	usr = session.get('username')
	if usr is None:
		g.username = 'Guest'
		session['username']='Guest'
	else:
		g.username = usr
		session['username']=usr
	cur = list(mongo.db.events.find({}, {'_id':False}))
	return render_template('index.html', username=g.username, events=cur)


@app.route("/register")
def register():
	return render_template('register.html')

#registrazione di un nuovo utente
@app.route("/create_user", methods=['POST'])
def create_user():
	error = None
	cur = None
	x = 0
	#accedo al mio db
	user = mongo.db.users
	#prendo i dati dal form con la request
	username = request.form['username']
	email = request.form['email']
	password1 = request.form['password1']
	password2 = request.form['password2']
	#controllo che abbia inserito tutti i campi
	if password1 != password2:
		error = 'Le password non coincidono!'
	if not email:
		error = 'Inserire una email'
	if '@' not in parseaddr(email)[1]:
		error = 'Inserire una email valida!'
	#controllo che non ci sia un altro utene con lo stesso username
	cur = user.find({'username':username})
	x = cur.count()
	if x != 0:
		error = 'Username gia in uso, inserirne uno diverso!'
		
	if error is None:
		#posso inserire il nuovo user
		user.insert({'username':username, 'password':generate_password_hash(password1), 'email':email})
		#ed effettuo il login aggiornando la sessione
		session.clear()
		session['username']=username
		usr = session.get('username')
		cur = list(mongo.db.events.find({}, {'_id':False}))
		return render_template('index.html', username=usr, events=cur, error=error)

	#lancio l'errore
	return render_template('register.html', error=error)

#login come ospite
@app.route("/login_as_guest")
def login_as_guest():
	session.clear()
	session['username']='Guest'
	usr = session.get('username')
	event = mongo.db.events
	cur = list(event.find({}, {'_id':False}))
	return render_template('index.html', username=usr, events=cur)

#login come utente
@app.route("/login_as_user", methods=['POST'])
def login_as_user():
	error = None
	cur = None
	x = 0
	#accedo al mio db
	user = mongo.db.users
	#prendo i dati dal form con la request
	username = request.form['username']
	password = request.form['password']
	#prendo l'utente dal db
	cur = user.find({'username':username})
	x = cur.count()
	inserted_password = list(cur)
	if x == 0:
		error = "L'utente che hai inserito non e' registrato !"
	else:
		if not check_password_hash(inserted_password[0]['password'], password):
			error = 'Password errata !'

	if error is None:
		#posso effettuare il login
		session.clear()
		session['username']=username
		usr = session.get('username')
		event = mongo.db.events
		cur = list(event.find({}, {'_id':False}))
		return render_template('index.html', username=usr, events=cur)

	return render_template('login.html', error=error)

@app.route("/login")
def login():
	return render_template('login.html')

@app.route("/create")
def create():
	usr = session.get('username')
	return render_template('create.html', username=usr)

#Creazione dell'evento
@app.route("/create_event", methods=['POST'])
def create_event():
	usr = session.get('username')
	#creo il mio evento
	creatore = usr
	nome = request.form['nome-evento']
	tipo = int(request.form['tipo-evento'])
	via = request.form['via-evento']
	comune = request.form['comune-evento']
	citta = request.form['citta-evento']

	try:
		datetime.datetime.strptime(request.form['data-evento'], "%Y-%m-%dT%H:%M")
	except ValueError:
		return render_template('create.html', error='Data non valida !')
	data_ora = datetime.datetime.strptime(request.form['data-evento'], "%Y-%m-%dT%H:%M")
	#stringa = creatore + ' ' + nome + ' ' + tipo + ' ' + indirizzo + ' ' + data_ora
	posti_occupati = 1
	posti_liberi = tipo * 2 - 1
	partecipanti = [creatore]
	#ricavo le coordinate
	query = via + ' ' + comune + ' ' + citta
	result = geocoder.geocode(query)
	longitude = result[0]['geometry']['lng']
        latitude  = result[0]["geometry"]["lat"]
	coordinate = [latitude, longitude]
	#inserisco nel db
	event = mongo.db.events
	#controllo che non ci sia un evento con uno stesso nome
	cur = event.find_one({'nome':nome})
	if cur is None:
		#controllo che non ci sia un evento con le stesse coordinate, nel caso aggiungo 0.0001*i
		cur = event.find({'$or':[{'coordinate':coordinate},{'indirizzo.via':via}]})
		x = cur.count()
		if x > 0:
			#ho gia un evento in quel posto, lo sposto un pochino
			coordinate[0] += x*0.0001
			coordinate[1] += x*0.0001

		#posso inserire il nuovo evento
		event.insert({
			'creatore':usr,
			'nome':nome,
			'tipo':tipo,
			'data':data_ora,
			'indirizzo':{'via':via, 'comune':comune, 'citta':citta},
			'liberi':posti_liberi,
			'occupati':posti_occupati,
			'partecipanti':partecipanti,
			'coordinate': coordinate
			})
		
		cur = list(event.find({}, {'_id':False}))
		return render_template('index.html', username=usr, events=cur)
	#devo cambiare nome all'evento
	return render_template('create.html', username=usr, error='Nome evento gia esistente !')

#Caricamento dell'iframe nel popup
@app.route("/join/<string:q>", methods=['GET','POST'])
def join(q):
	event = mongo.db.events
	cur = list(event.find({'nome':q}, {'_id':False}))
	date = json.dumps(cur[0]['data'].isoformat())
	newdate = date[1:17]
	tipo = cur[0]['tipo']
	liberi = cur[0]['liberi']
	creatore = cur[0]['creatore']
	indirizzo = cur[0]['indirizzo']['via']+', '+cur[0]['indirizzo']['comune']+', '+cur[0]['indirizzo']['citta']
	return render_template('join.html', nome=q, tipo=tipo, liberi=liberi, creatore=creatore, indirizzo=indirizzo, data=newdate)

#Operazione di Join ad un evento	
@app.route("/join_in/<string:q>", methods=['GET', 'POST'])
def join_in(q):
	event = mongo.db.events
	#controllo che l'evento esista ancora
	cur = list(event.find({'nome':q}, {'_id':False}))
	#setto tutti i campi che dovro ritornare
	date = json.dumps(cur[0]['data'].isoformat())
	newdate = date[1:17]
	tipo = cur[0]['tipo']
	liberi = cur[0]['liberi']
	creatore = cur[0]['creatore']
	indirizzo = cur[0]['indirizzo']['via']+', '+cur[0]['indirizzo']['comune']+', '+cur[0]['indirizzo']['citta']

	usr = session.get('username')
	#se non sei loggato non puoi joinare agli eventi
	if usr == 'Guest':
		error = 'Occorre effettuare il Login !'
		return render_template('join.html', nome=q, tipo=tipo, liberi=liberi, creatore=creatore, indirizzo=indirizzo, data=newdate, error=error)

	#controllo che l utente non partecipi gia all'evento
	partecipanti = list(event.find({'nome':q}, {'partecipanti':True, '_id':False}))
	for i in partecipanti[0]['partecipanti']:
		if str(i) == usr:
			error = 'Partecipi gia all evento !'
			return render_template('join.html', nome=q, tipo=tipo, liberi=liberi, creatore=creatore, indirizzo=indirizzo, data=newdate, error=error)
	#controllo che ci sia posto
	posti_totali = cur[0]['tipo'] *2
	posti_occupati = posti_totali - liberi
	if posti_occupati < posti_totali:
		#posso joinare al game
		posti_occupati += 1
		liberi = posti_totali - posti_occupati
		usr = session.get('username')
		#ora posso aggiornare l'evento
		event.update({'nome':q}, {'$set':{'occupati':posti_occupati, 'liberi':liberi}})
		#inserisco l'utente nei partecipanti
		event.update({'nome':q}, {'$push':{'partecipanti': usr}})	
	else:
		#non posso joinare
		error = 'Troppo tardi! Non ci sono posti! D;'
		return render_template('join.html', nome=q, tipo=tipo, liberi=liberi, creatore=creatore, indirizzo=indirizzo, data=newdate, error=error)
	return render_template('join.html', nome=q, tipo=tipo, liberi=liberi, creatore=creatore, indirizzo=indirizzo, data=newdate)

#Apre la pagina che mostra gli eventi a cui l'utente partecipa o che ha creato
@app.route("/eventi")
def eventi():
	usr = session.get('username')
	event = mongo.db.events
	cur = list(event.find({'$or':[{'creatore':usr}, {'partecipanti':{'$in':[usr]}}]}, {'_id':False}))
	return render_template('eventi.html', username=usr, events=cur)

#Elimina un evento.
#Se sei il creatore lo elimini per tutti i partecipanti
#Altrimenti ti rimuovi dai partecipanti
@app.route("/elimina", methods=['GET', 'POST'])
def elimina():
	usr = session.get('username')
	nome = request.form['evento']
	event = mongo.db.events

	#se sono il creatore allora elimino totalmente l'evento
	sono_creatore = event.find({'$and':[{'nome':nome}, {'creatore':usr}]})
	if sono_creatore.count() == 0:
		ev = event.find({'nome':nome}, {'_id':False})
		posti_occupati = ev[0]['occupati'] -1
		posti_liberi = ev[0]['liberi'] +1
		partecipanti = ev[0]['partecipanti']
		for index, elemento in enumerate(partecipanti):
			if elemento == usr:
				partecipanti.pop(index)
		#non sono il creatore, devo solo aggiornare l'evento della mia assenza
		event.update({'nome':nome}, {'$set':{'partecipanti':partecipanti, 'liberi':posti_liberi, 'occupati':posti_occupati}})
	else:
		#sono il creatore dell'evento, lo elimino completamente
		event.remove({'nome':nome})
	cur = list(event.find({'$or':[{'creatore':usr}, {'partecipanti':{'$in':[usr]}}]}, {'_id':False}))
	return render_template('eventi.html', username=usr, events=cur)

#Serce a vercare gli eventi in base al nome di un partecipante, al nome del creatore dell'evento o al nome dell'evento stesso
@app.route("/search", methods=['GET', 'POST'])
def search():
	usr = session.get('username')
	ricerca = request.form['ricerca']
	event = mongo.db.events
	cur = list(event.find({}, {'_id':False}))
	searched = list(event.find({'$or':[{'creatore':ricerca}, {'nome':ricerca}, {'partecipanti':{'$in':[ricerca]}}]}, {'_id':False}))	
	return render_template('index.html', username=usr, events=cur, searched=searched)
	