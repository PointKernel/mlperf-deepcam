import subprocess as sp
import numpy as np
import pandas as pd
from io import StringIO
import os
import re
import shutil
import sqlite3

def parse_filename_nsight(filename):
    #empty dicts
    result={}
    
    #add network name
    result["Network Name"] = "deepCam"
    result["Batch Size"] = int(re.match(r'.*\.batchsize_(.*?)\.',filename).groups()[0])
    result["Pass"] = re.match(r'.*\.pass_(.*?)\.',filename).groups()[0]
    result["Precision"] = "mixed"
    
    return result


def combine_metrics(df, metrics):
    return pd.DataFrame.from_records([{"Metric Count": df[m].values[0], "Metric Name": m.replace("read","").replace("write","").replace("__","_"), \
    "Metric Mode": "read" if "read" in m else "write" if "write" in m else "total"} for m in metrics])


def replace_tc_string(value):
    value = int(re.match(r".*?\((.*?)\)",value).groups()[0])
    return value


def import_nsight_metric(ImportFromNsight, filename, cuda_dir='/usr/local/cuda'):
    if not ImportFromNsight:
        profiledf = pd.read_csv(filename)
        return profiledf
    
    #execute nvprof and parse file
    args = [os.path.join(cuda_dir, "bin/nv-nsight-cu-cli"),"--csv","-i",filename]
    #skiprows = 2~
        
    #open subprocess and communicate
    p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = p.communicate()
    
    #get timeline from csv
    profiledf = pd.read_csv(StringIO(stdout.decode("utf-8")),skiprows=0) #.dropna(how="all").rename(columns={"Kernel": "Name"})
    
    #clean up
    del profiledf["Process ID"]
    del profiledf["Process Name"]
    del profiledf["Host Name"]
    del profiledf["Kernel Time"]
    del profiledf["Context"]
    del profiledf["Stream"]
    del profiledf["Section Name"]
    
    #profiledf = profiledf.groupby(["Kernel Name", "Metric Name"]).apply(lambda x: pd.Series([x["Metric Value"].count(),x["Metric Value"].sum()])).reset_index()
    #profiledf.rename(columns={0: "Invocations", 1: "Metric Value", "Kernel Name": "Name"}, inplace=True)
    #profiledf['Metric Value'] /=profiledf['Invocations']

    profiledf.rename(columns={"Kernel Name": "Name"}, inplace=True)
    filename = filename.replace('.ncu-rep','.csv')
    profiledf.to_csv(filename, encoding='utf-8', index=False)
    
    #return result
    return profiledf


def import_nsight_overview(filename):
    #execute nvprof and parse file
    conn = sqlite3.connect(filename)
    
    #do the query
    query_cuda = "SELECT end-start,StringIds.value FROM CUPTI_ACTIVITY_KIND_KERNEL INNER JOIN StringIds ON CUPTI_ACTIVITY_KIND_KERNEL.demangledName = StringIds.id"
    query_cublas = "SELECT end-start,StringIds.value FROM CUBLAS_EVENTS INNER JOIN StringIds ON CUBLAS_EVENTS.nameId = StringIds.id"
    query_cudnn = "SELECT end-start,StringIds.value FROM CUDNN_EVENTS INNER JOIN StringIds ON CUDNN_EVENTS.nameId = StringIds.id"

    #get dataframes
    dflist = []
    #read CUDA stuff
    tmpdf = pd.read_sql_query(query_cuda,conn)
    tmpdf.rename(columns={"value": "Kernel Name", "end-start": "Time"}, inplace=True)
    dflist.append(tmpdf)
    #read cublas stuff
    tmpdf = pd.read_sql_query(query_cublas,conn)
    tmpdf.rename(columns={"value": "Kernel Name", "end-start": "Time"}, inplace=True)
    tmpdf = tmpdf[ ~tmpdf["Kernel Name"].str.contains("cuBLASprofiling started") & ~tmpdf["Kernel Name"].str.contains("cuBLAS finished") ]
    if not tmpdf.empty:
        dflist.append(tmpdf)
    #read cudnn stuff
    tmpdf = pd.read_sql_query(query_cudnn,conn)
    tmpdf.rename(columns={"value": "Kernel Name", "end-start": "Time"}, inplace=True)
    tmpdf = tmpdf[ ~tmpdf["Kernel Name"].str.contains("cuDNNprofiling started") & ~tmpdf["Kernel Name"].str.contains("cuDNN finished") ]
    if not tmpdf.empty:
        dflist.append(tmpdf)
    
    #concat
    timedf = pd.concat(dflist)
    
    #add all the timings together
    tmpdf1 = timedf.groupby("Kernel Name").sum().reset_index()
    tmpdf2 = timedf.groupby("Kernel Name").count().reset_index()
    timedf = tmpdf1.merge(tmpdf2.rename(columns={"Time": "Invocations"}), on="Kernel Name")
    timedf["Time"] *= 1e-6
    timedf["Time Avg"] = timedf["Time"] / timedf["Invocations"]
    timedf.rename(columns={"Kernel Name": "Name"}, inplace=True)
    
    #return result
    return timedf
