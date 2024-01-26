# AUTHOR: DAVID TENA GAGO
def numberOfDigits(n):
    if n is not None:
        count=0
        if n == 0:
            return 1
        else:
            while(n>0):
                count=count+1
                n=n//10
            return count
    else:
        return -1

def positive(n):
    if n > 0:
        return True
    else:
        return False

def formatArgument5digits(value):
    digits = numberOfDigits(value)
    if digits == 1:
        return "0000" + str(value)
    elif digits == 2:
        return "000" + str(value)
    elif digits == 3:
        return "00" + str(value)
    elif digits == 4:
        return "0" + str(value)
    else:
        return str(value)
