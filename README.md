[![Build Status](https://travis-ci.org/ciorceri/logXchecker.svg?branch=master)](https://travis-ci.org/ciorceri/logXchecker)



# logXchecker

**logXchecker** is a ham radio contests log cross checker with the following features:

    - Support for EDI file format (VHF/UHF/SHF contests)
    - Support for Cabrillo V2.0 / V3.0 file format (HF contests)
    - Validator for individual logs
        - Generic syntax validator
        - Validate logs based on predefined rules
    - Output can have following formats: human-friendly, json, xml, csv
    - Cross checker to generate VHF and HF contest results
    
#### Future features:
    - Support for ADIF logs with generic and rules based validator

#### Usage
To run the tool using source code you need Python 3.7+

    - For Windows download and install from: https://www.python.org/downloads/
    - For Ubuntu install using:
        $ sudo apt-get update
        $ sudo apt-get install python3.7
        $ sudo apt-get install python3-pip
    - MacOS install using:
        $ brew install python3

Install tool requirements using command:

    $ cd logXchecker
    $ pip3 install -r requirements.txt

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
callregexp=.*
```

#### The rules format is based on [INI file format](http://en.wikipedia.org/wiki/INI_file) and there are the following sections:

    [contest]
        Contains generic details about contest:
            - name
            - contest date : begindate, enddate
            - contest hours : beginhour, endhour
            - bands : number of bands used in contest
            - periods : number of periods
            - categories : number of categories (sosb, momb, checklog, ...)
            - modes : (EDI/VHF) list with numeric valid contest modes: 1=ssb, 2=cw, 6=fm
              (Cabrillo/HF)  list with string valid contest modes: CW, SSB, DIGI, FM, AM, RTTY
            - custom_scoring : (optional) enables custom scoring engine (e.g. 'DRACULA' for Dracula contest)
    [log]
        Specifies the log format ('edi' for VHF/UHF contests, 'cabrillo' for HF contests)
    [band1], [band2], ... [bandN]
        Rules about contest bands (frequency)
            - band : band name to be used in report
            - regexp : customisable regular expresion field to detect band in logs 
            - multiplier : the points multiplier for this band (use 1 as default value)
    [period1], [period2], ... [periodN]
        Rules about contest periods
            - period date : begindate, enddate
            - period hours : beginhour, endhour
            - bands : list with contest bands that will be used in that period
    [category1], [category2], ... [categoryN]
        Rules about contest categories (single/multi operator[s], category bands)
            - name : category name to be used in report
            - regexp : customisable regular experesion field to detect ham category in logs
            - bands : list with allowed bands by that category (usually all bands)
    [extra]
        Rules for presence and validation of other header fields from log (email, address, name)
            Those fields can be required by contest managers who want to contact later the contest participants.
            Fields possible values : YES, any other value, not present
            - field 'email'
              If value is YES an email address is mandatory in log header
            - field 'address'
              If value is YES a contact address is mandatory in log header
            - field 'name'
              If value is YES an name is mandatory in log header
        Following setting can be used in national contests where we want to filter the callsigns
            - field 'callregexp' , possible values : not present, valid regular expresion
              If is present it must be a valid regular expression. Based on that regexp all callsigns and qso's will be filtered and crosscheck will be done only for allowed callsigns.
              Example : for 'YO national contest' this field value will have the value:
                callregexp=yo|yp|yq|yr
    [scoring]
        (Optional — only for HF/Cabrillo format) Configures custom point values and multipliers
            - qso_points : base points awarded per confirmed QSO (default: 1)
            - special_callsign : comma-separated list of special station callsigns
            - non_yo_to_special_points : points for non-YO station contacting a special station
            - non_yo_to_yo_points : points for non-YO station contacting a YO station
            - non_yo_dxcc_points : points for non-YO station contacting same-DXCC non-YO station
            - non_yo_same_country_points : points for non-YO station contacting same-country station
            - yo_to_special_points : points for YO station contacting a special station
            - yo_to_nonyo_points : points for YO station contacting a non-YO station
            - yo_to_yo_points : points for YO-YO QSO (usually 0 for HF contests)
            - multiplier_enabled : true/false — enables multiplier-based scoring
            - multiplier_per_band : true/false — compute multipliers independently per band
            - multiplier_exchange_field : which QSO exchange field carries the multiplier value (e.g. nr_recv)
            - multiplier_special_exchange : special exchange value that also counts as multiplier (e.g. 'DRC' or 'RRO')

#### HF rules format (for Cabrillo logs) — Dracula contest example:
```
[contest]
name=Dracula
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=5
periods=1
categories=7
modes=CW,SSB
custom_scoring=DRACULA

[log]
format=cabrillo

[band1]
band=3.5
regexp=3\.?|80m
multiplier=1

[band2]
band=7
regexp=7\.?|40m
multiplier=1

[band3]
band=14
regexp=14\.?|20m
multiplier=1

[band4]
band=21
regexp=21\.?|15m
multiplier=1

[band5]
band=28
regexp=28\.?|10m
multiplier=1

[period1]
begindate=20261031
enddate=20261101
beginhour=1200
endhour=1159
bands=band1,band2,band3,band4,band5

[category1]
name=SO-AB-HP SSB
regexp=A1
bands=band1,band2,band3,band4,band5

[category2]
name=SO-AB-HP CW
regexp=A2
bands=band1,band2,band3,band4,band5

[category3]
name=SO-AB-HP MIXT
regexp=A3
bands=band1,band2,band3,band4,band5

[category4]
name=SO-AB-LP SSB
regexp=B1
bands=band1,band2,band3,band4,band5

[category5]
name=SO-AB-LP CW
regexp=B2
bands=band1,band2,band3,band4,band5

[category6]
name=SO-AB-LP MIXT
regexp=B3
bands=band1,band2,band3,band4,band5

[category7]
name=MO-AB-HP MIXT
regexp=C
bands=band1,band2,band3,band4,band5

[scoring]
special_callsign=YP2DRACULA,YR2DRACULA,YQ2DRACULA,YP5DRACULA,YR5DRACULA,YQ5DRACULA,YP6DRACULA,YR6DRACULA,YQ6DRACULA
non_yo_to_special_points=10
non_yo_to_yo_points=5
non_yo_dxcc_points=2
non_yo_same_country_points=1
yo_to_special_points=10
yo_to_nonyo_points=5
yo_to_yo_points=0
multiplier_enabled=true
multiplier_per_band=true
multiplier_exchange_field=nr_recv
multiplier_special_exchange=DRC
```

#### Simple HF rules format (YODX contest example):
```
[contest]
name=YODX 2024
begindate=20240824
enddate=20240825
beginhour=1200
endhour=1159
bands=5
periods=1
categories=3
modes=CW,SSB

[log]
format=cabrillo

[band1]
band=3.5
regexp=3\.?|80m
multiplier=1

[band2]
band=7
regexp=7\.?|40m
multiplier=1

[band3]
band=14
regexp=14\.?|20m
multiplier=1

[band4]
band=21
regexp=21\.?|15m
multiplier=1

[band5]
band=28
regexp=28\.?|10m
multiplier=1

[period1]
begindate=20240824
enddate=20240825
beginhour=1200
endhour=1159
bands=band1,band2,band3,band4,band5

[category1]
name=Single
regexp=SINGLE|SINGLE-OP|SO
bands=band1,band2,band3,band4,band5

[category2]
name=Multi
regexp=MULTI|MULTI-OP|MO
bands=band1,band2,band3,band4,band5

[category3]
name=Checklog
regexp=CHECK|CHECKLOG
bands=band1,band2,band3,band4,band5

[scoring]
non_yo_to_yo_points=8
non_yo_dxcc_points=4
non_yo_same_country_points=1
yo_to_nonyo_points=8
yo_to_yo_points=0
multiplier_enabled=true
multiplier_per_band=true
multiplier_exchange_field=nr_recv
```

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

#### Cabrillo (HF) usage examples using the provided 'test_logs' folder:

* Single Cabrillo log validation (generic, no rules) and human friendly output
```
$ python3 ./logXchecker.py -slc ./test_logs/cabrillo/logs_raw/YO5PJB.log -f cabrillo
logXchecker - v1.0
Checking log : ./test_logs/cabrillo/logs_raw/YO5PJB.log
No error found
```

* Single Cabrillo log validation (with HF rules) and human friendly output
```
$ python3 ./logXchecker.py -slc ./test_logs/cabrillo/logs_raw/YO5PJB.log -r ./test_logs/rules_hf.config
logXchecker - v1.0
Checking log : ./test_logs/cabrillo/logs_raw/YO5PJB.log
QSO errors :
Line 21 : QSO: 14000 CW 2024-01-15 1205 YO5PJB          599 001 YO5BTZ          599 002 <- Qso date is invalid: not inside contest periods
```

* Single Cabrillo log validation (with HF rules) and json output
```
$ python3 ./logXchecker.py -slc ./test_logs/cabrillo/logs_raw/YO5PJB.log -r ./test_logs/rules_hf.config -o json
logXchecker - v1.0
{"log": "./test_logs/cabrillo/logs_raw/YO5PJB.log", "io": [], "header": [], "qso": [[21, "QSO: 14000 CW 2024-01-15 1205 ...", "Qso date is invalid: not inside contest periods"]]}
```

* Multiple Cabrillo logs validation (with HF rules) and human friendly output
```
$ python3 ./logXchecker.py -mlc ./test_logs/cabrillo/logs_raw/ -r ./test_logs/rules_hf.config
...
```

* Cabrillo logs cross-check (rules are mandatory) and human friendly output
```
$ python3 ./logXchecker.py -cc ./test_logs/cabrillo/logs_raw/ -r ./test_logs/rules_hf.config
...
```

* Dracula contest cross-check with custom scoring
```
$ python3 ./logXchecker.py -cc ./test_logs/cabrillo/logs_dracula/ -r ./test_logs/rules_hf_dracula.config
...
```

#### Example of possible Cabrillo log header validation errors:
```
Line None : CALLSIGN field is not present
Line None : CATEGORY-BAND field is not present
Line None : CATEGORY-OPERATOR field is not present
Line 1 : Missing or invalid START-OF-LOG header
Line 1 : Unsupported Cabrillo version: 1.0
```

#### Example of Cabrillo Qso errors:
```
QSO: 14000 RTTY 2026-10-31 1200 YO5PJB          599 CJ  YO5BTZ          599 001 : Qso mode is invalid: not in defined modes (CW,SSB)
QSO: 14000 CW 2026-10-30 1200 YO5PJB            599 CJ  YO5BTZ          599 001 : Qso date is invalid: before contest starts (<261031)
QSO: 14000 CW 2026-11-02 1200 YO5PJB            599 CJ  YO5BTZ          599 001 : Qso date is invalid: after contest ends (>261101)
QSO: 14000 CW 2026-10-31 1159 YO5PJB            599 CJ  YO5BTZ          599 001 : Qso hour is invalid: before contest start hour (<1200)
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
    - Only Python 3.10+ will be supported.
    - On request : I can provide MacOS and Windows builds to make Python install optional. 
