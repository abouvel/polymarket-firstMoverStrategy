from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

async def fetch_markets():
    transport = AIOHTTPTransport(url="https://api.gamma.xyz/graphql")
    client = Client(transport=transport, fetch_schema_from_transport=True)
    
    query = gql("""
    query {
        markets(first: 10, orderBy: creationTimestamp, orderDirection: desc) {
            id
            question
            outcomeType
        }
    }
    """)
    
    async with client as session:
        result = await session.execute(query)
        return result["markets"]
    