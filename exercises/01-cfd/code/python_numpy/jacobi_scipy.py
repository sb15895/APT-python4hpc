# 
# Jacobi function for CFD calculation
#
# Basic Python version using lists
#

import sys
import numpy as np 
import numexpr 
from scipy import ndimage 
def jacobi(niter, psi):

    # Get the inner dimensions
    m = len(psi) - 2
    n = len(psi[0]) -2

    # Define the temporary list and zero it
    # tmp = [[0 for col in range(n+2)] for row in range(m+2)]
    tmp = np.zeros((m+2, n+2))

    weights = [
    [0,1,0],
    [1,0,1],
    [0,1,0] 
    ] 

    psi_temp = np.zeros((3,3))
    # Iterate for number of iterations
    for iter in range(1,niter+1):

        # Loop over the elements computing the stream function
        for i in range(1,m+1):
            for j in range(1,n+1):
                psi_temp = psi[i-1:i+2][i-1:i+2, j-1:j+2] 
                tmp[i,j] = ndimage.convolve(psi_temp,weights,mode='constant', cval=0.25)
                exit() 

        # array index slicing to optimise updates         
        psi[:] = tmp[:] 

        # Debug output
        if iter%1000 == 0:
            sys.stdout.write("completed iteration {0}\n".format(iter))
