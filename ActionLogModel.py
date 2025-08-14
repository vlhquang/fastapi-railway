import time
import json
import logging

MEMBER_TYPE_NORMAL = "normal"
MEMBER_TYPE_STANDARD = "standard"
MEMBER_TYPE_PRO = "pro"

class DataModule1Config:
    def __init__(self, memberType: str, jsonConfig: str):
        self.memberType = memberType
        self.countCallAPI = jsonConfig.get("countCallAPI", 0)
        self.countCallAPIConfig = jsonConfig.get("countCallAPIConfig", 3)

    def allowSearchAPI(self):
        if self.memberType == MEMBER_TYPE_NORMAL:
            return False
        else:
            return self.countCallAPI <= self.countCallAPIConfig
    
    def allowSearchDB(self):
        return self.countCallAPI <= self.countCallAPIConfig
    
    def increaseCountCallAPI(self):
        self.countCallAPI += 1
        return self.countCallAPI
    
    def toString(self):
        return {
            "countCallAPI": self.countCallAPI,
            "countCallAPIConfig": self.countCallAPIConfig
        }

class ActionLogModel:
    def __init__(self, actionLogDB: str):
        self.memberType = actionLogDB.get("memberType", MEMBER_TYPE_NORMAL)
        self.jsonActionLogDB = actionLogDB

    def getDataModule1(self):
        return DataModule1Config(self.memberType, self.jsonActionLogDB.get("module1", {}))
    
    def toJson(self, dataModule1Config: DataModule1Config = None):
        return json.dumps({
            "memberType": self.memberType,
            "module1": dataModule1Config.toString()
        })