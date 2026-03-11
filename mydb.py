import mysql.connector

dataBase = mysql.connector.connect(
  host = 'localhost',
  user = 'root',
  passwd = '968841'
)


# prepare a cursor object 
cursorObject = dataBase.cursor() 

# Create a database 
cursorObject.execute("CREATE DATABASE sheepdb12")

print("All Done!")