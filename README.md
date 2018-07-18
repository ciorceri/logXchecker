[![Build Status](https://travis-ci.org/ciorceri/logXchecker.svg?branch=master)](https://travis-ci.org/ciorceri/logXchecker)



# logXchecker

**logXchecker** is a ham radio contests log cross checker with the following features:

    - Support for EDI file format
    - Validator for individual logs
        - Generic syntax validator
        - Validate logs based on predefined rules
    - Output can have following formats: human-friendly, json, xml
    - Cross checker to generate a VHF contest results
    
#### Future features:
    - Support for ADIF & Cabrillo logs with generic and rules based validator
    
#### Current VHF rules format (this format may be subject to change):
```
[contest]
name=Contest name
begindate=20180701
enddate=20180702
beginhour=1200
endhour=1800
bands=2
periods=2
categories=3
modes=1,2,6

[log]
format=edi

[band1]
band=144
regexp=144|145|2m
multiplier=1

[band2]
band=432
regexp=430|432|435|70cm
multiplier=2

[period1]
begindate=20180701
enddate=20180701
beginhour=1200
endhour=1800
bands=band1,band2

[period2]
begindate=20180702
enddate=20180702
beginhour=1200
endhour=1800
bands=band1,band2

[category1]
name=Single Operator
regexp=so|single
bands=band1

[category2]
name=Multi Operator
regexp=mo|multi
bands=band1,band2

[category3]
name=Checklog
regexp=check|checklog
bands=band1,band2

[extra]
email=yes
address=no
name=yes
```

#### The rules format is based on [INI file format](http://en.wikipedia.org/wiki/INI_file) and there are the following sections:

    [contest]
        contains generic details about contest:
            - name
            - contest date : begindate, enddate
            - contest hours : beginhour, endhour
            - bands : number of bands used in contest
            - periods : number of periods
            - categories : number of categories (sosb, momb, checklog, ...)
            - modes : list with valid contest modes (1=ssb, 2=cw, 6=fm)
    [log]
        specifies the log format (only edi is supported at this moment)
    [band1], [band2], ... [bandN]
        rules about contest bands (frequency)
            - band : band name to be used in report
            - regexp : customisable regular expresion field to detect band in logs 
            - multiplier : the points multiplier for this band (use 1 as default value)
    [period1], [period2], ... [periodN]
        rules about contest periods
            - period date : begindate, enddate
            - period hours : beginhour, endhour
            - bands : list with contest bands that will be used in that period
    [category1], [category2], ... [categoryN]
        rules about contest categories (single/multi operator[s], category bands)
            - name : category name to be used in report
            - regexp : customisable regular experesion field to detect ham category in logs
            - bands : list with allowed bands by that category (usually all bands)
    [extra]
        rules presence and validation of other header fields from log (email, address, name)

#### Run examples using the provided 'test_logs' folder:
* Single log validation (generic, no rules) and human friendly output
```
$ python3 ./logXchecker.py -slc ./test_logs/logs/yo2lza_20160514_091251.edi -f edi
logXchecker - v1.0
Checking log : ./test_logs/logs/yo2lza_20160514_091251.edi
No error found
```
* Single log validation (generic, no rules) and json output
```
$ python3 ./logXchecker.py -slc ./test_logs/logs/yo2lza_20160514_091251.edi -f edi -o json
logXchecker - v1.0
{"log": "./test_logs/logs/yo2lza_20160514_091251.edi", "io": [], "header": [], "qso": []}
```
* Single log validation (with rules) and human friendly output
```
$ python3 ./logXchecker.py -slc ./test_logs/logs/yo2lza_20160514_091251.edi -r ./test_logs/rules.config
logXchecker - v1.0
Checking log : ./test_logs/logs/yo2lza_20160514_091251.edi
QSO errors :
Line 226 : 160508;1201;OM3RLA;1;59;186;59;185;;JN98LB;349;;;; <- Qso date/hour is invalid: not inside contest periods
Line 227 : 160508;1213;IQ8BI;1;59;187;59;076;;JN71HU;679;;;; <- Qso date/hour is invalid: not inside contest periods
```
* Single log validation (with rules) and json output
```
$ python3 ./logXchecker.py -slc ./test_logs/logs/yo2lza_20160514_091251.edi -r ./test_logs/rules.config -o json
logXchecker - v1.0
{"log": "./test_logs/logs/yo2lza_20160514_091251.edi", "io": [], "header": [], "qso": [[226, "160508;1201;OM3RLA;1;59;186;59;185;;JN98LB;349;;;;", "Qso date/hour is invalid: not inside contest periods"], [227, "160508;1213;IQ8BI;1;59;187;59;076;;JN71HU;679;;;;", "Qso date/hour is invalid: not inside contest periods"]]}
```
* Multiple logs validation (with rules) and human friendly output
```
$ python3 ./logXchecker.py -mlc ./test_logs/logs/ -r ./test_logs/rules.config 
...
```
* Logs cross-check (rules are mandatory) and human friendly output
```
$ python3 ./logXchecker.py -cc ./test_logs/logs -r ./test_logs/rules.config
...
```
* Logs + checklogs cross-check (rules are mandatory) and human friendly output
```
$ python3 ./logXchecker.py -cc ./test_logs/logs -cl ./test_logs/checklogs/ -r ./test_logs/rules.config
...
```
* Logs + checklogs cross-check (rules are mandatory) and verbose human friendly output
```
$ python3 ./logXchecker.py -cc ./test_logs/logs -cl ./test_logs/checklogs/ -r ./test_logs/rules.config -v
...
```

#### Example of possible errors at log header validation:
```
Line None : PCall field is not present
Line None : PWWLo field is not present
Line None : PBand field is not present
Line None : PSect field is not present
Line None : TDate field is not present
Line 3 : TDate field value is not valid (20180701;2018)
Line 4 : PCall field content is not valid
Line 5 : PWWLo field value is not valid
```

#### Example of possible errors at log header validation when rules are provided:
```
Line 3 : TDate field value has an invalid value (20160507;20160508). Not as defined in contest rule
Line 9 : PSect field value has an invalid value (SINGLE). Not as defined in contest rules
```

#### Example of Qso errors:
```
160507;1450;LZ7J;1;59;006;59;019;;KN22HB;362;;N;; : No log from LZ7J
160507;1529;LZ2SQ;1;59;008;59;020 KN33GY;;;234;;N;; : Qso field <rst received nr> has an invalid value (020 KN33GY)
160507;1549;LZ2JA;1;59;010;59;009;;KN22UA;357;;;; : Qth locator mismatch
```
   
#### Notes:
    - Suggestions are appreciated.
    - Only Python 3.6+ will be supported.
    - I will provide MacOS and Windows builds to make Python install optional. 
