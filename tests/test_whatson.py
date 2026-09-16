import unittest
from whatson import normalize

class WhatsonTests(unittest.TestCase):
 def test_active_progress_and_provider_mapping(self):
  rows=[{'title':'Example','status':'watching','current_episode':3,'current_season':2,'service':'Apple TV+','poster_url':'https://image.tmdb.org/t/p/w342/example.jpg'}]
  show=normalize(rows)[0]
  self.assertEqual(show['service_id'],'apple-tv')
  self.assertEqual(show['episode'],3)
  self.assertTrue(show['poster'])
 def test_caught_up_and_hiatus_excluded(self):
  self.assertEqual(normalize([{'status':'watching','current_episode':99},{'status':'hiatus','current_episode':1}]),[])
 def test_unconfigured_service_and_untrusted_poster(self):
  show=normalize([{'status':'watching','current_episode':1,'service':'Unsupported provider','poster_url':'https://example.com/private'}])[0]
  self.assertIsNone(show['service_id'])
  self.assertEqual(show['poster'],'')
