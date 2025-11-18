# Temporal Graph Memory

Mycelia stores objects in a single collection `objects`. Together objects form a graph where edges are objects with `relationship.object` and `relationship.subject` references to other objects.


```javascript
{
  "_id": "68f76e7be53242f4de49524f",
  "name": "Me",
  "isPerson": true,
}

{
  "_id": "68fbb2549c7fb0a8e15df259",
  "name": "Amsterdam",
  "icon": {"text": "🇳🇱"},
  "details": "Capital of the Netherlands",
  "location": {
    "latitude": 52.37,
    "longitude": 4.89
  }
}

{
  "_id": "68fd63eded122e76740db8c4",
  "name": "lives in",
  "isRelationship": true,
  "isEvent": true,
  "relationship": {
    "subject": "68f76e7be53242f4de49524f",  // Me
    "object": "68fbb2549c7fb0a8e15df259",    // Amsterdam
    "symmetrical": false
  },
  "timeRanges": [
    {
      "start": "2022-12-23T12:00:00Z",
      "end": null,  // Still ongoing
    }
  ],
  "version": 1
}
```

