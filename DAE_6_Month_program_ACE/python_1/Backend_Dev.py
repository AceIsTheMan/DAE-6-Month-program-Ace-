# Testing functions

username = input("Name?: ")

# Gender selection

while gender != "Male" or gender != "Female" or gender != "Other":
    input(f"{username} Is Male. Female, or Other?: ")
    gender = input("Male, Female, Other?: ")

    if gender == "Male":
        gender = "Mr"
    elif gender == "Female":
        gender = "Mrs"
    elif gender == "Other":
        gender = "The"
#==================================
# Gender Wall (fix line 7)
#==================================


hometown = input("Where are you from?: ")

def greet_user():
    print ("=====================")
    print (f"Hello {username} from {hometown}.")
    print (f"How may I be of service ")
    print ("=====================")