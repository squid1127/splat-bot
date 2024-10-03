# MySQL libs
import mysql.connector

# Load environment variables for the database
import dotenv
import os

# Table creator
import tabulate

dotenv.load_dotenv()

# Connect to the database
mydb = mysql.connector.connect(
    host=os.getenv('MYSQL_HOST'),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DATABASE')
)

# Create a cursor
mycursor = mydb.cursor()

print("Connected to the database")

# try:
#     mycursor.execute("SHOW TABLES")
#     myresult = mycursor.fetchall()
#     print("Tables in the database:")
#     for x in myresult:
#         print("- ",x[0])
# except Exception as e:
#     print("Error grabing tables")
#     print(e)
try:
    while True:
        query = input("MySQL> ")
        if query == 'exit':
            break
        try:
            mycursor.execute(query)
            #mydb.commit()
            print("Query executed successfully")

            # read the result
            result = mycursor.fetchall()
            try:
                print(tabulate.tabulate(result, headers=mycursor.column_names, tablefmt="simple_grid"))
            except:
                myresult = mycursor.fetchall()
                for x in myresult:
                    print(x)
        except Exception as e:
            print("Error executing query")
            print(e)
except KeyboardInterrupt:
    print("\nBye bye!")
        