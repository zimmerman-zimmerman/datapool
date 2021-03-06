# -*- coding: utf-8 -*-
import pyorient
from lxml import etree
from lxml import objectify
from io import StringIO, BytesIO
from dateutil.parser import parse
import json
import re
import pprint
from filegrabber import FileGrabber
import models

"""
	generic class with datapool functions for OrientDB

"""
class DataPool():
	db_name = 'datapool'
	user_name = 'root'
	password = 'solaria07'
	xml_tree = None
	schema = None
	prefix = 'iati105'
	max_rows_to_delete = 9999
	file_to_parse = None
	schema_properties = {}
	schema_classes = {}
	schema_edges = {}
	encoding = 'ascii'
	create_schema = False
	source = None



	"""
		create class in orientdb
	"""
	def create_class(self,data_model_class):

		cluster_ids = self.client.command('create class '+data_model_class.orient_name+' EXTENDS V ')
		cluster_id = cluster_ids[0]
		cluster_ids = self.client.command("select classes[name='"+data_model_class.orient_name+"'].defaultClusterId FROM 0:1")		
		cluster_id = cluster_ids[0].classes
		print 'cluster_id = '+str(cluster_id)
		data_model_class.default_cluster_id = str(cluster_id)
		data_model_class.save()
		return cluster_id

	"""
		create model in django
	"""
	def create_model(self,class_name):
		class_name = class_name.strip()
		data_model_class = models.DataModelClass()
		data_model_class.name = class_name.strip()
		data_model_class.translated_name = class_name
		data_model_class.orient_name = class_name
		#data_model_class.default_cluster_id = cluster_id
		data_model_class.data_source = self.source
		data_model_class.save()
		self.schema_classes[class_name] = {}
		#self.schema_classes[class_name]['cluster_id'] = cluster_id
		self.schema_classes[class_name]['django_object'] = data_model_class
		return data_model_class
		

	"""
		create property django model
	"""

	def create_property_model(self,class_name,property_name,data_model_class):
		property_name = property_name.strip()
		prop_name =self.format_attrib_name(property_name)
		self.schema_properties[class_name+'.'+prop_name] = True
		data_model_class_property = models.DataModelProperty()
		data_model_class_property.data_model_class = data_model_class
		data_model_class_property.name = prop_name
		data_model_class_property.translated_name = prop_name
		data_model_class_property.orient_name = self.format_attrib_name(prop_name)

		data_model_class_property.type = 'STRING'
		data_model_class_property.save()
		if 'date' in prop_name:
			data_model_class_property_iso_ = models.DataModelProperty()
			data_model_class_property_iso_.data_model_class = data_model_class
			data_model_class_property_iso_.name = prop_name+'__iso__'
			data_model_class_property_iso_.type = 'DATETIME'
			data_model_class_property_iso_.save()


	"""
		create property in orientdb
	"""
	def create_property(self,data_model_class_property):
		type_conversion ={'STRING':'STRING',
	    				'INTEGER':'LONG',
	    				'FLOAT':'DOUBLE',
	    				'TEXT':'STRING',
	    				'DATE':'DATE',
	   					'DATETIME':'DATETIME',
	    				'LAT':'FLOAT',
	    				'LONG':'FLOAT',
	    				'LAT LONG':'STRING',
	    				'SCRIPT':'STRING',
	   					'TIMESTAMP':'DATETIME',
	    				'TIMESTAMPMILLIS':'DATETIME'}
	   	prop_type = type_conversion[data_model_class_property.get_property_type_display()]
	

		print 'create property '+data_model_class_property.data_model_class.name+'.'+data_model_class_property.orient_name+' '+prop_type
		self.client.command('create property '+data_model_class_property.data_model_class.name+'.'+data_model_class_property.orient_name+' '+prop_type)
		if prop_type == 'TEXT':
			self.client.command('create index '+data_model_class_property.data_model_class.name+'.'+data_model_class_property.orient_name+' on '+data_model_class_property.data_model_class.name+' ('+data_model_class_property.orient_name+') FULLTEXT ENGINE LUCENE')




	"""
		create edge in orient db
	"""
	def create_edge(self,from_rec,to_rec,edge_name,parent,child):
		edge_command = "CREATE edge "+edge_name.encode(self.encoding)+" from "+from_rec+" to "+to_rec
		try:
			self.client.command(edge_command)
		except Exception as exception:
			self.create_edge_object(edge_name,parent,child)
			self.client.command(edge_command)
	
	"""
		create edge class in orientdb
	"""
	def create_edge_object(self,django_edge):
		edge_command = "create class "+django_edge.name.encode(self.encoding)+" extends E"

		#add edge to list

		self.client.command(edge_command)
		self.client.command('CREATE PROPERTY '+django_edge.name.encode(self.encoding)+'.out LINK '+django_edge.class_out.name.encode(self.encoding))
		self.client.command('CREATE PROPERTY '+django_edge.name.encode(self.encoding)+'.in LINK '+django_edge.class_in.name.encode(self.encoding))
		

	"""
		create edge class in django
	"""
	def create_edge_model(self,edge_name,parent_object,child_object):
		django_edge = models.DataModelEdge()
		django_edge.name = edge_name
		django_edge.class_out = parent_object
		django_edge.class_in = child_object
		django_edge.data_source = self.source
		django_edge.save()
		self.schema_edges[edge_name] = django_edge
		return django_edge



	def connect(self,db_name,user_name,password,host,port,prefix):
		self.client = pyorient.OrientDB(host, port)
		print user_name+' '+password
		self.client.connect(user_name.encode(self.encoding),password.encode(self.encoding))
		self.client.db_open(db_name, user_name,password )
		self.prefix = prefix

	def close(self):
		self.client.db_close()


	def connect_old(self):
		self.client = pyorient.OrientDB("localhost", 2424)
		self.client.connect(self.user_name,self.password)
		self.client.db_open(self.db_name, self.user_name,self.password )

	def delete_classes(self,drop_class=False):
		list_command = "SELECT classes FROM 0:1"
		classes = self.client.command(list_command)
		for clss in classes[0].classes:
			print clss.get('name')
			print clss.get('superClass')
			if str(clss.get('name')).startswith(self.prefix):
				#get number of rows

				#numrows = result[0]['num_rows']

				type_class = 'EDGE'
				if(clss.get('superClass') == 'V'):
					type_class = 'VERTEX'
				print 'TRUNCATE CLASS '+clss.get('name')+' UNSAFE'
				self.client.command('TRUNCATE CLASS '+clss.get('name')+' UNSAFE')
					
				if drop_class == True:
					print 'DROP CLASS '+clss.get('name')
					self.client.command('DROP CLASS '+clss.get('name'))


	"""
		return STRING
		try and format the tag name to properly work in orientdb  (TODO: this does not check for lenghts or keywords)
	"""
	def format_class_name(self,tag_name):
		#replace minus
		tag_name = re.sub("(\{.*\})","",tag_name) 
		tag_name = tag_name.replace('-','_')
		tag_name = tag_name.replace('"','').encode(self.encoding)
		
		return self.prefix+'_'+tag_name.replace(' ','_')

	def format_attrib_name(self,tag_name):
		#replace minus
		#tag_name = self.remove_prefixes(tag_name)
		tag_name = re.sub("(\{.*\})","",tag_name) 
		tag_name = tag_name.replace('-','_')
		tag_name = tag_name.replace('"','')
		tag_name = tag_name.replace('(','_')
		tag_name = tag_name.replace(')','_')
		tag_name = tag_name.replace(':','_')
		tag_name = tag_name.replace('/','')
		tag_name = tag_name.replace('-','')
		return tag_name.replace(' ','').encode(self.encoding)

	"""
		beginning of escaping 
	"""
	def escape_orientdb(self,text):
		escapechars = '@()"%'
		for special_char in escapechars:
			text = text.replace(special_char,'\\'+special_char)
		return text

	"""
		create structure for tree view
	"""
	def make_structure(self):
		query = 'SELECT classes FROM 0:1'
		db_classes = self.client.command(query)

		edges = {}
		classes = {}
		data_tree = {}
		for db_class in db_classes:
			for db_class_info in db_class.classes:
				if not str(db_class_info['name']).startswith(self.prefix):
					continue
				if db_class_info['superClass'] in ['E']:
					edges[db_class_info['name']] = {}
					for db_property in db_class_info['properties']:
						edges[db_class_info['name']][db_property['name']] = db_property['linkedClass']
				if db_class_info['superClass'] in ['V']:
					classes[db_class_info['name']] = {}
					for db_property in db_class_info['properties']:
						classes[db_class_info['name']][db_property['name']] = db_property['type']
		
		#loop through edges to make get parents
		parent_data = {}
		child_data = {}
		for key in edges:
			edge = edges[key]
			parent_data[edge['in']] = edge['out']
			if(edge['out'] not in child_data):
				child_data[edge['out']] = []
			child_data[edge['out']].append(edge['in'])


		#find root edge
		root = ''

		for key in parent_data:
			if(parent_data[key] not in parent_data):
				root = parent_data[key]
		if len(parent_data) == 0:
			#only one class
			root = self.prefix

		structure_tree = {}
		self.make_tree(root,child_data,structure_tree,classes)
		
		return structure_tree


	def load_url(self, url):
		filegrabber = FileGrabber()
		self.file_to_parse = file_grabber.get_the_file(url)
		

	"""
		create tree
	"""
	def make_tree(self,element_name,child_data,tree_dict,classes):

		tree_dict[element_name] = {}
		tree_dict[element_name]['attributes'] = classes[element_name]
		first_loop = True
		if element_name not in child_data:
			return
		for sub_element in child_data[element_name]:
			#first
			if first_loop == True:
				tree_dict[element_name]['subclasses'] = {}
				first_loop = False

			self.make_tree(sub_element,child_data,tree_dict[element_name]['subclasses'],classes)
		return 



	def format_for_d3(self,structure_tree):
		d3_tree = {'name':'data','size':100,'children':[]}
		for element in structure_tree:
			self.make_d3_tree(element,structure_tree[element],d3_tree['children'])

		json_tree = json.dumps(d3_tree)
		print json_tree


	def make_d3_tree(self,element_name,element,sub_structure_tree):
		element_data = {'name':str(element_name).replace(self.prefix+'_',''),'size':100}
		element_data['attributes'] = element['attributes']
		element_data['children'] = []
		
		for attr_name in element['attributes']:
			element_data['children'].append({'name':'attribute '+attr_name})
		if not 'subclasses' in element:
			sub_structure_tree.append(element_data)
			return
		for sub_class in element['subclasses']:	
			self.make_d3_tree(sub_class,element['subclasses'][sub_class],element_data['children'])

		
		
		sub_structure_tree.append(element_data)

	"""
		create pivot pont between data set NOT NUSED YET IMPLEMENTATION NOT COMPLETE

	"""
	def create_pivot(self,from_class,to_class,from_match, to_match):
		class_name = from_class+"_"+to_class
		query = 'CREATE CLASS '+class_name+'_pivot EXTENDS V'
		#self.client.command(query)
		query = 'CREATE PROPERTY '+class_name+'.match STRING'
		#self.client.command(query)
		edge_to_name = ''
		query = 'CREATE CLASS '+class_name+' EXTENDS E'
		#self.client.command(query)
		query = "SELECT "+from_match+' FROM '+from_class+' GROUP BY '+from_match
		matches = self.client.command(query)
		for match in matches:
			print match.get('from_match')

	def parse(self):
		pass

	def remove_prefixes(self,prop_name):
		prefixes = self.source.remove_prop_strings.rstrip().split('\n')
		for prefix in prefixes :
			if not ':%:' in prefix: 
				print prefix+'  prop name ='+prop_name
				prop_name = prop_name.replace(prefix.rstrip(),'')
			else:
				prefix_arr = prefix.rstrip().split(':%:')
				prop_name = prop_name.replace(prefix_arr[0].rstrip(),prefix_arr[1].rstrip())
			
		return prop_name

	def load_schema(self):
		#load schema from django models
		source = self.source
		#get classes
		classes = models.DataModelClass.objects.filter(data_source=source)
		for data_model_class in classes:
			cluster_ids = self.client.command("select classes[name='"+data_model_class.name+"'].defaultClusterId FROM 0:1")
			print "select classes[name='"+data_model_class.name+"'].defaultClusterId FROM 0:1"
			
			cluster_test = cluster_ids[0].classes

			if (not isinstance( cluster_test, int )) and len(cluster_test) == 0:
				models.DataModelProperty.objects.filter(data_model_class=data_model_class).delete()
				data_model_class.delete()
				print len(cluster_ids[0].classes)
				print 'deleted'
				print 'exiting'
				continue
			
			#print data_model_class.name
			self.schema_classes[data_model_class.name] = {}
			self.schema_classes[data_model_class.name]['cluster_id'] = data_model_class.default_cluster_id
			self.schema_classes[data_model_class.name]['django_object'] = data_model_class
			
			for class_prop in models.DataModelProperty.objects.filter(data_model_class=data_model_class):
				self.schema_properties[data_model_class.name+'.'+class_prop.name] = {}
				self.schema_properties[data_model_class.name+'.'+class_prop.name]['has_prop'] = True
				self.schema_properties[data_model_class.name+'.'+class_prop.name]['django_object'] = class_prop
				
		for data_model_edge in models.DataModelEdge.objects.filter(data_source=source):
			cluster_ids = self.client.command("select classes[name='"+data_model_edge.name+"'].defaultClusterId FROM 0:1")
			try:
				cluster_test = cluster_ids[0].classes
			except:
				data_model_edge.delete()
				continue
			self.schema_edges[data_model_edge.name] = data_model_edge

	"""

		create the schema in orient db from the djnago models
	"""
	def create_orient_schema(self):
		source = self.source
		#get classes
		classes = models.DataModelClass.objects.filter(data_source=source).all()
		for data_model_class in classes:
			self.create_class(data_model_class)

			
			for class_prop in models.DataModelProperty.objects.filter(data_model_class=data_model_class).all():
				
				self.create_property(class_prop)
				
		for data_model_edge in models.DataModelEdge.objects.filter(data_source=source).all():
			self.create_edge_object(data_model_edge)


	"""
		query orient db
	"""
	def get_query_data(self,data_set,post_data):
		connection = data_set.data_stream.data_connection
		self.connect(connection.name,connection.username,connection.password,connection.host,connection.port,self.prefix)
		#make query
		query_data_set = {}
		property_type_set = {}
		search_boxes = {}
		for data_set_property in data_set.properties.all():
			if not data_set_property.use_property:
				continue
			if data_set_property.get_action_display() == 'SEARCHBOX':
				search_boxes['param_'+str(data_set_property.id)] = {'name':data_set_property.data_model_property.translated_name,'type':data_set_property.data_model_property.get_property_type_display()}
			add_field = True
			if  (data_set_property.get_action_display() == 'SEARCHBOX' or data_set_property.get_action_display() == 'FILTER') and data_set_property.show_filter_field != True:
				add_field = False
			if add_field :
				property_type_set[data_set_property.data_model_property.orient_name] = {}
				property_type_set[data_set_property.data_model_property.orient_name]['type'] = data_set_property.data_model_property.get_property_type_display()
				property_type_set[data_set_property.data_model_property.orient_name]['action'] = data_set_property.get_action_display()
			action_list = data_set_property.ACTIONCHOICE
			class_name = data_set_property.data_stream_class.name
			if not class_name  in query_data_set:
				query_data_set[class_name] = QueryData()
				query_data_set[class_name].parameters = post_data
				query_data_set[class_name].class_name = class_name
				query_data_set[class_name].order_by = data_set.x_axis.data_model_property.orient_name
			query_data = query_data_set[class_name]
			
			query_data.fields[action_list[data_set_property.action][1]].append(data_set_property)
		query_result = []
		for query_data in query_data_set:
			query = query_data_set[query_data].make_query().encode(self.encoding)
			result = self.client.query(query)
			temp_data = []
			for row in result:
				temp_data.append(row.oRecordData)
			#make datatype array

			query_result.append({'query':query,'data_stream':data_set.name,'property_type_set':property_type_set,'graph':data_set.get_chart_type_display(),'x_axis':data_set.x_axis.data_model_property.orient_name,'data':temp_data , 'search_boxes':search_boxes})
			
		self.close()
		return query_result
		

	def format_data_for_graph(self):
			pass
	def run_regex(self,col_value,col_obj):
		for regexp in col_obj.regexp.all():
			col_value = re.sub(regexp.script,'',col_value)
		
		print col_value+' after regex'
		return col_value



"""
	clas for managing query building
"""
class QueryData:
	
	class_name = ''
	order_by = ''
	fields = {}
	parameters = {}

	def __init__(self):
		actionlist = models.DataSetStreamProperty.ACTIONCHOICE
		for action in actionlist:
			self.fields[action[1]] = []


	"""
		make the query based on the values of DataStreamClass and DataStreamProperties
	"""
	def make_query(self):
		pprint.pprint(self.parameters)
		#set filter fields
		filter_query_arr = []
		for filter_field in self.fields['SEARCHBOX']:
			if filter_field.show_filter_field == True:
				self.fields['SELECT'].append(filter_field)
			param_name = 'param_'+str(filter_field.id)
			filter_type = filter_field.data_model_property.get_property_type_display()
			if param_name in self.parameters and self.parameters[param_name] != '':
				param_value = self.parameters[param_name]
				if filter_type == 'TEXT':
					filter_query_arr.append(filter_field.data_model_property.orient_name+" LUCENE '"+param_value+"'")
				elif filter_type == 'INTEGER' :
					filter_query_arr.append(filter_field.data_model_property.orient_name+' = '+param_value)
				else:
					filter_query_arr.append(filter_field.data_model_property.orient_name+" = '"+param_value+"'")

		for filter_field in self.fields['FILTER']:
			if filter_field.show_filter_field == True:
				self.fields['SELECT'].append(filter_field)
			filter_value = filter_field.filter_value
			if filter_value == '' or filter_value == None:
				continue
			filter_type = filter_field.data_model_property.get_property_type_display()
			if filter_type == 'TEXT':
				filter_query_arr.append(filter_field.data_model_property.orient_name+" LUCENE '"+filter_value+"'")
			elif filter_type == 'INTEGER' :
				
				filter_query_arr.append(filter_field.data_model_property.orient_name+' = '+filter_value)
			else:
				filter_query_arr.append(filter_field.data_model_property.orient_name+" = '"+filter_value+"'")
		filter_query = ' AND '.join(filter_query_arr)


		group_by_fields =  ','.join([field.data_model_property.orient_name for field in self.fields['SELECT']])

		sum_fields =  ','.join(['SUM('+field.data_model_property.orient_name+') AS '+field.data_model_property.orient_name for field in self.fields['SUM']])
		avg_fields =  ','.join(['AVG('+field.data_model_property.orient_name+') AS '+field.data_model_property.orient_name for field in self.fields['AVG']])
		min_fields =  ','.join(['MIN('+field.data_model_property.orient_name+') AS '+field.data_model_property.orient_name for field in self.fields['MIN']])
		max_fields =  ','.join(['MAX('+field.data_model_property.orient_name+') AS '+field.data_model_property.orient_name for field in self.fields['MAX']])
		count_fields =  ','.join(['COUNT('+field.data_model_property.orient_name+') AS '+field.data_model_property.orient_name+'_count' for field in self.fields['COUNT']])
		




		select_query = ','.join(filter(bool,[sum_fields,avg_fields,min_fields,max_fields,group_by_fields,count_fields]))
		# todo filter fields
		# and searhcbox fields
		from_query = ' FROM '+self.class_name

		group_by_query = ''
		if group_by_fields > '' and group_by_fields != select_query: 
			group_by_query = ' GROUP BY '+group_by_fields
		if filter_query != '':
		 	filter_query = ' WHERE '+filter_query

		query = 'SELECT '+select_query+from_query+filter_query+group_by_query+' ORDER BY '+self.order_by+' LIMIT 10000'
		print query
		return query


















