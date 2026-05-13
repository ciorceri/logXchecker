Below are few example on how to run the validation and cross-check for HF and VHF contest

HF contest, RRO 2024:
- validate a single log without any rules
python .\logXchecker.py -slc .\test_logs\cabrillo\logs_rro\YO2ARM.log --format cabrillo
- validate a single log with rules
python .\logXchecker.py -slc .\test_logs\cabrillo\logs_rro\YO2ARM.log --rules .\test_logs\rules_hf_rro_2024.config
- validate all logs without any rules (qso date/hour is not validated) ("logs_raw" folder contains also invalid logs)
python .\logXchecker.py -mlc .\test_logs\cabrillo\logs_rro\ --format cabrillo
python .\logXchecker.py -mlc .\test_logs\cabrillo\logs_raw\ --format cabrillo
- validate all logs using the rules (qso date/hour is validated) ("logs_raw" folder contains also invalid logs)
python .\logXchecker.py -mlc .\test_logs\cabrillo\logs_rro\ --rules .\test_logs\rules_hf_rro_2024.config
python .\logXchecker.py -mlc .\test_logs\cabrillo\logs_raw\ --rules .\test_logs\rules_hf_rro_2024.config
- cross check
python .\logXchecker.py -cc .\test_logs\cabrillo\logs_rro\ --rules .\test_logs\rules_hf_rro_2024.config

VHF contest, Napoca Cup 2016
- validate a single log without any rules
python .\logXchecker.py -slc .\test_logs\edi\logs_napoca_cup_2016\adrian_20160514_202826.edi --format edi
- validate a single log with rules
python .\logXchecker.py -slc .\test_logs\edi\logs_napoca_cup_2016\adrian_20160514_202826.edi --rules .\test_logs\rules_vhf_napoca_2016.config
- validate all logs without any rules (qso date/hour is not validated)
python .\logXchecker.py -mlc .\test_logs\edi\logs_napoca_cup_2016\ --format edi
- validate all logs using the rules (qso date/hour is validated)
python .\logXchecker.py -mlc .\test_logs\edi\logs_napoca_cup_2016\ --rules .\test_logs\rules_vhf_napoca_2016.config
- cross check
python .\logXchecker.py -cc .\test_logs\edi\logs_napoca_cup_2016\ --rules .\test_logs\rules_vhf_napoca_2016.config

Crosscheck output format :
python .\logXchecker.py -cc .\test_logs\cabrillo\logs_rro\ --rules .\test_logs\rules_hf_rro_2024.config -o HUMAN-FRIENDLY
python .\logXchecker.py -cc .\test_logs\cabrillo\logs_rro\ --rules .\test_logs\rules_hf_rro_2024.config -o JSON
python .\logXchecker.py -cc .\test_logs\cabrillo\logs_rro\ --rules .\test_logs\rules_hf_rro_2024.config -o XML
python .\logXchecker.py -cc .\test_logs\cabrillo\logs_rro\ --rules .\test_logs\rules_hf_rro_2024.config -o CSV
