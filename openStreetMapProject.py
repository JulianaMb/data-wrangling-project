
# coding: utf-8

# Loading data

# In[2]:

import xml.etree.cElementTree as ET
import pprint
import re
import codecs
import json
from collections import defaultdict
from pymongo import MongoClient


# In[3]:

k = 100 # Parameter: take every k-th top level element
SAMPLE_FILE = "mapsimple.xml"
xmlFile = "map.xml"

def get_element(xml_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag

    Reference:
    http://stackoverflow.com/questions/3095434/inserting-newlines-in-xml-file-generated-via-xml-etree-elementtree-in-python
    """
    context = iter(ET.iterparse(xml_file, events=('start', 'end')))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


with open(SAMPLE_FILE, 'wb') as output:
    output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    output.write('<osm>\n  ')

    # Write every kth top level element
    for i, element in enumerate(get_element(xmlFile)):
        if i % k == 0:
            output.write(ET.tostring(element, encoding='utf-8'))

    output.write('</osm>')


# In[4]:

CREATED = [ "version", "changeset", "timestamp", "user", "uid"]
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')

#Changing this regex to match brasilian names of streets
street_type_re = re.compile(r'^\b\S+\.?', re.IGNORECASE)
street_types = defaultdict(set)


expected = [u"Rua", u"Avenida", u"Travessa", u"Beco", u"Rodovia", u"Estrada", u"Logradouro", u"Viela", u"Alameda", u"Via", u"Praça"]

# UPDATE THIS VARIABLE
mapping = { "R": "Rua",
            "R.": "Rua",
            "r." : "Rua",
            "rua": "Rua",
            "RUA": "Rua",
            "Rua-": "Rua ",
            "Ruas": "Rua",
            "Av.": "Avenida",
            "AV.": "Avenida",
            "AVENIDA":"Avenida",
            "Alamenda": "Alameda",
            "Rodovoa": "Rodovia"
            }


def audit_street_type(street_types, street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)

def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way" :
        node["type"]=element.tag        
        
        for at in element.attrib:
            if at in CREATED :
                if node.get("created") == None:
                    node[u"created"] = {}
                node[u"created"].update({at : element.get(at)})
            elif at in "lon":
                if node.get("pos") ==None:
                    node[u"pos"] = [0,1]
                node[u"pos"][1] = float(element.get(at))
            elif at in "lat":
                if node.get("pos") ==None:
                    node[u"pos"] = [0,1]
                node[u"pos"][0]= float(element.get(at))
            else: 
                node[at] = element.get(at)
        for child in element:
            
            if child.get("k"):      
                if problemchars.search(child.get("k")):
                    continue                    
                elif re.search(':',child.get("k")) != None:
                    name = child.get("k").split(":")
                    if node.get(name[0]) == None:                            
                        node[name[0]] = {}
                    if name[1]==u"street":
                        audit_street_type(street_types, child.get("v"))
                    node[name[0]].update({name[1] : child.get("v")})                            
                else:
                    if node.get("caract")==None:
                        node[u"caract"]={}                        
                    node[u"caract"].update({child.get("k"):child.get("v")})
            if element.tag == "way":                
                if child.tag == "nd":                     
                    if node.get("node_refs") == None:
                        node[u"node_refs"] = []
                    node[u"node_refs"].append(child.get("ref"))                       
            
        return node
    else:
        return None

def key_type(element, keys):
    if element.tag == "way":
        for tag in element.iter("tag"):
            k = tag.get("k")
            if lower.search(k):
                keys['lower'] +=1
            elif lower_colon.search(k):
                keys['lower_colon'] +=1
            elif problemchars.search(k):
                keys['problemchars'] +=1
            else:
                keys['other'] +=1
    
    return keys    

def process_keys(file_in):
    keys = {"lower": 0, "lower_colon": 0, "problemchars": 0, "other": 0}
    for event, element in ET.iterparse(file_in, events=("start",)):
        keys = key_type(element, keys)
        
    return keys    
    
    
def process_map(file_in, pretty = False):
    #street_types = defaultdict(set)
    file_out = "{0}.json".format(file_in)
    data = []
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data

def update_name(name):
    m = street_type_re.search(name)
    if m:
        if m in mapping:
            name = name.replace(m.group(), mapping[m.group()])
    
    return name

def audit_street_name(data):
    for tupla in data:        
        if tupla.get('addr'):                   
            if tupla.get('addr').get('street'):
                name = tupla.get('addr').get('street')
                tupla.get('addr')['street'] = update_name(name)
    


# In[5]:

data = process_map(xmlFile, True)

#auditing street names 
audit_street_name(data)


# In[14]:

client = MongoClient("mongodb://localhost:27017")
db = client['goiania']
#drop the documents if exists to avoid append the same data twice
db.goiania.drop();



# In[15]:

print db


# In[16]:

db.goiania.insert_many(data)
print db.goiania.find_one()


# In[17]:

db.goiania.find().count()


# In[32]:


user = db.goiania.distinct("created.user")

print len(user)


# In[33]:

#quantity contribution by user
query = []
query.append({"$group" : {"_id" : "$created.user", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
query.append({"$limit" : 10})

result = db.goiania.aggregate(query)

for doc in result:
    pprint.pprint(doc)


# In[20]:

#user that have the most number of contributions
query = []
query.append({"$group" : {"_id" : "$created.user", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
query.append({"$limit" : 1})

result = db.goiania.aggregate(query)

for doc in result:
    pprint.pprint(doc)


# In[58]:

#unique contributors
query = []

query.append({"$group" : {"_id" : "$created.user", "count":{"$sum":1}}})
query.append({"$match" : {"count" : 1}})

result = db.goiania.aggregate(query)
print len(list(db.goiania.aggregate(query))) 

for doc in result:
    pprint.pprint(doc)
    
   


# In[21]:

#quantity by type (node\way)
query = []
query.append({"$group" : {"_id" : "$type", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})

result = db.goiania.aggregate(query)

for doc in result:
    pprint.pprint(doc)


# In[22]:

#amenities
db.goiania.distinct("caract.amenity")


# In[34]:

#quantity amenities
query = []
query.append({"$group" : {"_id" : "$caract.amenity", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
query.append({"$limit" : 10})

result = db.goiania.aggregate(query)

for doc in result:
    pprint.pprint(doc)


# In[24]:

#streets
db.goiania.distinct("addr.street")


# In[45]:
#streets without street info
query = []
query.append({"$match":{"addr.street": {"$eq": "Qd4 Lt10"}}})

result = db.goiania.aggregate(query)

for doc in result:
    pprint.pprint(doc)


# In[25]:
#all the documents that street starts with Qd
result = db.goiania.find({"addr.street": {'$regex': '^Qd', '$options': 'i'}})
print db.goiania.find({"addr.street": {'$regex': '^Qd', '$options': 'i'}}).count()
print db.goiania.find({"addr.street": {'$regex': '^Qd', '$options': 'i'}}).distinct("created.user")
for doc in result:
    print pprint.pprint(doc)
    



# In[28]:
#finding the regex
string = "74.110-100"
print re.match(r"^74\.?\d{3}\-?\d{3}$", string)

# In[29]:


#count quantity of addr tags
print db.goiania.find({"addr": {'$exists': True}}).count()           
#count quantity of addr tags with street information
print db.goiania.find({"addr.street": {'$exists': True}}).count()
#postcodes are like the regex?
print db.goiania.find({"addr.postcode":{'$exists':True}}).count()
print db.goiania.find({"addr.postcode":{'$exists':True, "$not": re.compile(r"^74\.?\d{3}\-?\d{3}$")}}).count()
postcodes = db.goiania.find({"addr.postcode":{'$exists':True, "$not": re.compile(r"^74\.?\d{3}\-?\d{3}$}")}})
for doc in postcodes:
    print pprint.pprint(doc)
#checking out the cities of wrong postcodes 
print db.goiania.find({"addr.postcode":{'$exists':True, "$not": re.compile(r"^74\.?\d{3}\-?\d{3}$")}}).distinct("addr.city")


# In[30]:

#amenity: restaurant cousine
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'restaurant'}}).distinct("caract.cuisine")
#most frequent cuisine 
query = []
query.append({"$match":{"caract.amenity":{"$exists": True, "$eq": u'restaurant'}}})
query.append({"$group" : {"_id" : "$caract.cuisine", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
cuisine = db.goiania.aggregate(query)
for doc in cuisine:
    print pprint.pprint(doc)
	
#amenity: restaurant cousine
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'fast_food'}}).distinct("caract.cuisine")
#most frequent cuisine 
query = []
query.append({"$match":{"caract.amenity":{"$exists": True, "$eq": u'fast_food'}}})
query.append({"$group" : {"_id" : "$caract.cuisine", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
cuisine = db.goiania.aggregate(query)
for doc in cuisine:
    print pprint.pprint(doc)	

#amenity: postal_office user geocorreios
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'post_office'}}).distinct("created.user")

#addr suburb (bairro)
print db.goiania.find({"addr.suburb":{"$exists": True}}).count()
query = []
query.append({"$match":{"addr.suburb":{"$exists": True}}})
query.append({"$group" : {"_id" : "$addr.suburb", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
#bairros = db.goiania.aggregate(query)                                          
#for doc in bairros:
 #   print pprint.pprint(doc)


# In[36]:

#amenity: place_of_worship
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'place_of_worship'}}).distinct("caract.religion")
#most frequent religion
query = []
query.append({"$match":{"caract.amenity":{"$exists": True, "$eq": u'place_of_worship'}}})
query.append({"$group" : {"_id" : "$caract.religion", "count":{"$sum":1}}})
query.append({"$sort" : {"count": -1}})
religion = db.goiania.aggregate(query)
for doc in religion:
    print pprint.pprint(doc)


# In[61]:

#information about the most common amenity parking

parking = db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'parking'}})
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'parking'}}).count()
print db.goiania.find({"$and" : [{"caract.amenity":{"$exists": True, "$eq": u'parking'}}, {"addr":{"$exists": True}}]}).count()


#for doc in parking:
 #   print pprint.pprint(doc)


# In[60]:

#information about quantity of addr in the amenities restaurant
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'restaurant'}}).count()
print db.goiania.find({"$and" : [{"caract.amenity":{"$exists": True, "$eq": u'restaurant'}}, {"addr":{"$exists": True}}]}).count()


# In[62]:

#information about quantity of addr in the amenities fuel
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'fuel'}}).count()
print db.goiania.find({"$and" : [{"caract.amenity":{"$exists": True, "$eq": u'fuel'}}, {"addr":{"$exists": True}}]}).count()


# In[63]:

#information about quantity of addr in the amenities bank
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'bank'}}).count()
print db.goiania.find({"$and" : [{"caract.amenity":{"$exists": True, "$eq": u'bank'}}, {"addr":{"$exists": True}}]}).count()


# In[40]:

#information about the second most common amenity fuel

fuel = db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'fuel'}})
print db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'fuel'}}).distinct("caract.brand")


#for doc in parking:
 #   print pprint.pprint(doc)


# In[41]:

#information about school
school = db.goiania.find({"caract.amenity":{"$exists": True, "$eq": u'school'}})

#for doc in school:
  #  print pprint.pprint(doc)





