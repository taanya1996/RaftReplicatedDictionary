import rsa
import os

for i in range(1, 6):
    public_key, private_key = rsa.newkeys(1024)
    fname = os.path.join(os.getcwd(),'keys/public'+str(i)+'.pem')
    print(fname)
    os.makedirs(os.path.dirname(fname), exist_ok=True)

    with open(fname, "w") as f:
        f.write(public_key.save_pkcs1().decode('utf-8'))
        f.close()

    fname = os.path.join(os.getcwd(),'keys/private'+str(i)+'.pem')
    os.makedirs(os.path.dirname(fname), exist_ok=True)

    with open(fname, "w") as f:
        f.write(private_key.save_pkcs1().decode('utf-8'))
        f.close()
    
