/**
 * GraphQL client adapter for service contract fixture.
 * Uses Node.js built-in http module only.
 */

import { requestHttp } from "./http-client.js";

/**
 * Execute a GraphQL operation against the fixture server.
 * @param {object} input - { operation, variables? }
 * @returns {Promise<{status: number, headers: object, data?: object, errors?: object[]}>}
 */
export async function executeGraphql({ operation = "", variables = {} }) {
  const query = operation.includes("query") ? operation : `query ${operation}($id: ID!) { order(id: $id) { id status items } }`;
  const { status, headers, body } = await requestHttp({
    method: "POST",
    path: "/graphql",
    body: { query, variables },
  });

  return {
    status,
    headers,
    data: body.data || null,
    errors: body.errors || null,
  };
}

export default executeGraphql;
