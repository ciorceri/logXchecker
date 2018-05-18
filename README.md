[![Build Status](https://travis-ci.org/ciorceri/logXchecker.svg?branch=master)](https://travis-ci.org/ciorceri/logXchecker)



# logXchecker

**logXchecker** is a ham radio contests log cross checker with the following features:

    - Support for EDI file format
    - Validator for individual logs
        - Generic syntax validator
        - Validate logs based on predefined rules
    - Output can have following formats: human-friendly, json, xml
    - Cross checker to generate a VHF contest results
Future features:

    - Support for ADIF & Cabrillo logs with generic and rules based validator
    
Current VHF rules format (this format may be subject to change):
```
[contest]
name=Cupa Nasaud
begindate=20160805
enddate=20160806
beginhour=1200
endhour=1200
bands=2
periods=2
categories=3

[log]
format=edi

[band1]
band=144
regexp=(144|145|2m)

[band2]
band=432
regexp=(430|432|70cm)

[period1]
begindate=20160805
enddate=20160805
beginhour=1200
endhour=2359
bands=band1,band2

[period2]
begindate=20160806
enddate=201608086
beginhour=0000
endhour=1200
bands=band1,band2

[category1]
name=Single Operator 144
regexp=(so|single)
bands=band1

[category2]
name=Single Operator 432
regexp=(so|single)
bands=band2

[category3]
name=Multi Operator
regexp=(mo|multi)
bands=band1,band2

[extra]
email=yes
address=no
name=yes
```
The rules format is based on [INI file format](http://en.wikipedia.org/wiki/INI_file).
There are the following sections:

    [contest]
        contains generic details about contest (name, contest date, contest hours, bands, periods and categories
    [log]
        specifies the log format (edi, adif, cabrillo)
    [band1], [band2], ... [bandN]
        rules about contest bands (frequency)
    [period1], [period2], ... [periodN]
        rules about contest periods (begin/end date, begin/end hour, bands)
    [category1], [category2], ... [categoryN]
        rules about contest categories (single/multi operator[s], category bands)
    [extra]
        rules presence and validation of other header fields (email, address, name)

The following errors can be displayed if validation fails:

    - Line None : PCall field is not present
    - Line None : PWWLo field is not present
    - Line None : PBand field is not present
    - Line None : PSect field is not present
    - Line None : TDate field is not present
    - Line 4 : PCall field content is not valid
    - Line 5 : PWWLo field value is not valid
    - Line 3 : TDate field value is not valid (201605070;20160508)

If a rules file was provided the following errors can be displayed if validation fails:
    - Rules validation errors:
      - ...
    - Log file validation errors:
      - ...

Notes:

    - This is a work in progress and there are still more things to add.
    - Suggestions are appreciated.
    - Only Python 3.6+ will be supported.
