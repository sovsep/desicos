import logging
import numpy as np
import numpy.ma as ma
import copy
import time
import sys
#sys.path.append( '/home/pavel/Documents/desicos/abaqus-conecyl-python_DEV')
from  st_utils.coords import *
from imperf import Samples
from conecylDB import*


class SamplesCC(Samples):
    def __init__(self,conecylDBFile):
        Samples.__init__(self)
        self.outName=None
        self.scalingFactor=1.0
        self.samplingRadial=256
        self.samplingAxial=128
        if conecylDBFile != None:
            self.ccdb=ConeCylDB(conecylDBFile)
        else:
            self.ccdb=ConeCylDB()

    def setCCDB(self,fname):
        self.ccdb=ConeCylDB(fname)
    def setRadialSampling(self,val):
        self.samplingRadial=val

    def setAxialSampling(self,val):
        self.samplingAxial=val

    def setOutputName(self,name):
        self.outName=name

    def setImpType(self,imp_type):
        self.imp_type=imp_type

    def copyPropsFromCCDB(self,imp_name):
        try:
            self.cc0=self.ccdb.getEntry(imp_name)
        except:
            logging.warning("ERROR: "+str(imp_name)+" is not in CC database!")
            return


    def importFromCCDB(self,imp_name,imp_type):

        IMP=self.ccdb.getEntry(imp_name)
        if IMP == None:
            logging.warning(str(imp_name)+" is not in IMPERFECTION database!")
        try:
            self.imp_type
        except:
            self.setImpType(imp_type)
        if imp_type != self.imp_type:
            logging.warning("You can`t mix imperfection types! \n Create SamplesCC instance for each type of imperfection")
            return


        if self.imp_type == 'ms':
            b=IMP.getGeometricImperfection()
        if self.imp_type == 'thick':
            b=IMP.getThicknessImperfection()
        if b == None:
            logging.warning(str(imp_name)+" with imperfection "+str(imp_type)+" is not in IMPERFECTION database!")
            return
        (H,R,alpha)=IMP.getGeometry()
        self.importFromXYZ(b,H,R,alpha)


    def importFromXYZ(self,b,H,RB,alpha):
        RT=RB-H *( np.tan(alpha ) )
        x,y,z=b[:,0],b[:,1],b[:,2]
        r,tht,z=rec2cyl(x,y,z)
        self.setGeometry(RB,H,alpha)
        rPerf=self._getRperf(z)
        if self.imp_type == 'thick':
            imp=b[:,3]
        else:
            imp=getGeomImperfection(r,z,rPerf)

        tm1=ma.masked_less(tht,0.1*np.pi).mask
        tm2=ma.masked_greater(tht,1.9*np.pi).mask

        tht=np.hstack((tht, np.pi*2.0+tht[tm1],  0.0+(-1.0)*tht[tm2]))
        r=np.hstack((r,r[tm1],r[tm2] ))
        z=np.hstack((z,z[tm1],z[tm2]))
        imp=np.hstack((imp,imp[tm1],imp[tm2]))

        ft=np.linspace(0,2.0*np.pi,self.samplingRadial)
        fz=np.linspace(0,H,self.samplingAxial)
        IMPERF=getImperfectionArray(tht,z,imp,ft,fz)

        mf=[]
        for row in IMPERF[0:len(IMPERF)]:
            mf.append( np.isnan(np.sum(row))  )
        row1=mf.index(False)
        mr=[]
        for i in reversed(mf):
            mr.append(i)
        row2= len(mf)-1-mr.index(False)

        row1+=1
        row2-=2
        dr1=row1
        rows1=range(0,row1)
        rows1sym=range(row1,row1+dr1)[::-1]

        dr2=len(mf)-1-row2
        rows2=range(len(mf)-1,row2,-1)
        rows2sym=range(row2-dr2,row2)[::-1]

        IMPERF[rows1]=IMPERF[rows1sym].copy()
        IMPERF[rows2]=IMPERF[rows2sym].copy()

        #EXTRUDE
        #IMPERF[0:row1]=IMPERF[row1]
        #IMPERF[row2::]=IMPERF[row2]

        self.addData(IMPERF,ft,fz)

    def getNewSampleXYZ(self):
        thtZ=self.getNewSample()
        tht=np.squeeze(np.tile(self.x,(1,len(self.y) )))
        z=np.repeat(self.y,len(self.x))
        r=self._getRperf(z)
        res=np.reshape(thtZ,len(tht),order='C')
        res=res*self.scalingFactor
        if self.imp_type == 'ms':
            r+=res
        x,y,z=cyl2rec( r, tht, z )
        if self.imp_type == 'ms':
            return np.hstack((x[np.newaxis].T , y[np.newaxis].T , z[np.newaxis].T))
        else:
            return np.hstack((x[np.newaxis].T , y[np.newaxis].T , z[np.newaxis].T , res[np.newaxis].T ))


    def putNewSampleToFolder(self,path):
        if self.outName == None :
            sname='AutogeneratedSample'+'_'+self.imp_type+'_'+time.strftime("%d_%B_%Y_%H_%M_%S_UTC",time.gmtime())
        else:
            sname=copy.copy(self.outName)
            self.outName = None
        try:
            os.makedirs(path)
        except:
            pass

        np.savetxt(path+sname,self.getNewSampleXYZ() )
        logging.info('saved:'+path+sname)


    def putNewSampleToCCDB(self,R=None,H=None,alpha=None):
        rcc=self.RB
        hcc=self.H
        acc=self.alpha

        if R != None:
            rcc=R
        if H != None:
            hcc=H
        if alpha != None:
            acc=alpha

        if self.outName == None :
            sname='AutogeneratedSample'+'_'+time.strftime("%d_%B_%Y_%H_%M_%S_UTC",time.gmtime())
        else:
            sname=copy.copy(self.outName)
            self.outName = None
        self.ccdb.copy(self.cc0.name,sname)
        newCE=self.ccdb.getEntry(sname)
        newCE.setGeometry(hcc,rcc,acc)

        if self.imp_type == 'thick':
            logging.info('Adding : '+str(sname)+'_'+str(self.imp_type)+' to CCDB')
            newCE.setThicknessImperfection(self.getNewSampleXYZ())
            logging.info('saved:'+sname)
        else:
            logging.info('Adding : '+str(sname)+'_'+str(self.imp_type)+' to CCDB')
            newCE.setGeometricImperfection(self.getNewSampleXYZ())
            logging.info('saved:'+sname)