
print("welcome to ace's Home")

# Hardcoding these values to represent the user's credentials
correct_username = "Ace"
correct_password = "AceTheMan"
# Give user wants to try again an initial value true / 1
user_wants_to_try_again = 1

# Ask the user for their username
user_name = input("Please enter your username: ")
password = input("Thank you. Also please type in your password: ")

while user_name != correct_username or password != correct_password:
    # Ask the user for their username
    print( "At least one credential is incorrect. Please renter: ")
    user_name = input("Username, Incorrect. Please enter your username: ")
    password = input("Password, Incorrect. Thank you. Also please type in your password: ")

print("Welcome" , user_name )

# Try again
while user_wants_to_try_again:
    at_home = int(input("Where are you? Press 1 for home. 0 for work.: ") )
    raining = int(input("Is it raining? press 1 for Yes and 0 for no.: ") )

    if raining and at_home:
        print("Stay home")
    elif raining and not at_home:
        print("stay at work")
    elif at_home:
        print("Go to work")
    elif not at_home:
        print("Go home") 

    print("Thank you for using this application")


    user_response = input("Do you want to use this again. Please type y/n: ")

    while user_response != "y" and user_response != "n":
        user_response = input("Hey please enter a y or n. Nothing else!")

    if user_response == "y":
        user_wants_to_try_again = 1
    else:
        user_wants_to_try_again = 0

print("bye!")

"""
The Red King
"""

# ART = """
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
#                                                                      11                                                                     
#                                                                      11                                                                     
#                                                                      11                                                                     
#                                                                     1111                                                                    
#                                                                     1111                                                                    
#                                                                    11111                                                                    
#                                                                    111111                                                                   
#                                     1                              11 111                              1                                    
#                                      11                         111111111111                          11                                    
#                                       11              1    1111111111111111111111    1              111                                     
#                                        111            11111111    11111111    11111111             111                                      
#                                         111         111111        1 1111 1        111111         1111                                       
#                                 11       11111    1111              1111             11111     11111      1                                 
#                                   111     1111  1111               11111               11111  1111     111                                  
#                                    11111  11111111                 111111                1111111111 1111                                    
#                                       11111 11111                  111111                  11111111111                                      
#                                         11111111111                111111                111 11111111                                       
#                                        11  1111 1111                1111               1111  111111111                                      
#                                       111 111   111                 1111                 111  111111111                                     
#                                      111  111  11111          11   11111    1           1111   111  111                                     
#                                     111   11    111111         111 1 1111 111         111111   111   111                                    
#                                  111111   11      11111         11  11111111      11 11111     111   1111                                   
#                                    111   111       111111       111111111111       111111      111    111                                   
#                                  11111   111        11111111   11111111111111  111111111        111   111111                                
#                                   111111 11         1 11111111111       1111111111111 1         111  11111                                  
#                                  111111111111111111111111111 1111        111111 111111111   11 11111111111111                               
#                           11111111111111111111111111111111111111            11111111111111111111111111111111111111                          
#                          11111111111111111111111111111111111111111        111111111111111111111111111111111111111111                        
#                                   1111111111111111111111111 11111   1111   1111  111111111  11111111111111                                  
#                                    11111 111              11111111  111   11111111         11111111 11111                                   
#                                  11111     1111         1111111111111   111111111111     11111111     11111                                 
#                                 11  11      1111111             11111  11111           111111111      11  11                                
#                                     111      1111111            11111  11111          11111111       111                                    
#                                      111    1  11111111        111111  11111       111111111 111     11                                     
#                                       11         111111111     1  111  111 11     11111111          11                                      
#                                         1       1111111111111     111  111   1111111111111  1      1                                        
#                                                 111111111111111111111  111111111111111111111                                                
#                                                111111  11111111111111  1111111111111111111111                                               
#                                               1111 1    11     111111  1111 11   111   111111                                               
#                                             1111       111        111  111        111      1111                                             
#                                            111         11         111 1111  1     111         111                                           
#                                          111           111        111 1111        111           11                                          
#                                         1              1          111 1111          1             11                                        
#                                                                   111 1111 1                                                                
#                                                               111 111 1111 111                                                              
#                                                            111111 111 1111 111111                                                           
#                                                          111111 11111 111111 111111                                                         
#                                                          111      111 1111     1111                                                         
#                                                         11        111  111       111                                                        
#                                                       11          111  111         111                                                      
#                                                     1             111  111           111                                                    
#                                                                  111111111              1                                                   
#                                                                   11111111                                                                  
#                                                                  111111111                                                                  
#                                                                  111111111                                                                  
#                                                                   1111111111                                                                
#                                                                   111  111 1                                                                
#                                                                   111  111                                                                  
#                                                                   111  111                                                                  
#                                                                   11111111                                                                  
#                                                                   111 111                                                                   
#                                                                   1111111                                                                   
#                                                                    111111                                                                   
#                                                                    111111                                                                   
#                                                                    111111                                                                   
#                                                                    111111                                                                   
#                                                                    11111                                                                    
#                                                                     1111                                                                    
#                                                                     1111                                                                    
#                                                                     111                                                                     
#                                                                      11                                                                     
#                                                                      11                                                                     
#                                                                      11                                                                     
#                                                                      1                                                                      
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
                                                                                                                                            
#                                                                                                                                             """

# print(ART)