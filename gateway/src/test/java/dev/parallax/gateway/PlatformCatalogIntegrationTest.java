package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.platform.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
        "parallax.gateway.require-auth=true", "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef", "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformCatalogIntegrationTest {
    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired JdbcTemplate jdbc;
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;
    private record Fixture(String user, String org, String project) { }
    private Fixture fixture() {
        var u=identity.provision("test", "catalog-"+UUID.randomUUID(), "test-password-123");
        var org=identity.createOrganization(u.id(), "team");
        return new Fixture(u.id(),org.id(),identity.createProject(u.id(),org.id(),"project").id());
    }
    private PlatformCatalogService.PolicyConfig config(long budget) {
        return new PlatformCatalogService.PolicyConfig(4,2,3,2,true,budget,3600);
    }
    private ResponseEntity<Map> call(HttpMethod method, String path, String user, Object body) {
        var h=new HttpHeaders(); h.setBearerAuth(jwt.issueUserToken(user,"test"));
        return rest.exchange(path,method,new HttpEntity<>(body,h),Map.class);
    }
    private String base(Fixture f) { return "/api/v1/platform/projects/"+f.project; }

    @Test
    void httpAuthorizationAndResourceOwnershipAreEnforced() {
        var owner=fixture(); var other=fixture();
        var response=call(HttpMethod.POST,base(owner)+"/repositories",owner.user,
                Map.of("name","api","cloneUrl","https://github.com/team/api.git"));
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        String id=(String)response.getBody().get("id");
        assertThat(call(HttpMethod.GET,base(owner)+"/repositories/"+id,other.user,null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(call(HttpMethod.GET,base(other)+"/repositories/"+id,other.user,null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        identity.addMember(owner.user,owner.org,other.user,ProjectRole.VIEWER);
        assertThat(call(HttpMethod.GET,base(owner)+"/repositories/"+id,other.user,null).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.POST,base(owner)+"/policies",other.user,config(100)).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        identity.removeMember(owner.user,owner.org,other.user);
        assertThat(call(HttpMethod.GET,base(owner)+"/repositories/"+id,other.user,null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void rejectsPathsCredentialsUnapprovedHostsAndInvalidPolicies() {
        var f=fixture();
        for(String url:List.of("file:///etc/passwd","http://github.com/a/b","https://127.0.0.1/a/b",
                "https://github.com:443/a/b","https://user:password@github.com/a/b","https://github.com/a/../b",
                "https://github.com/a/%2e%2e/b","https://github.com/a/b?token=secret","https://github.com/a/b#fragment",
                "https://github.com.evil.example/a/b","ssh://git@github.com/a/b")) {
            assertThatThrownBy(()->catalog.register(f.user,f.project,"bad",url)).isInstanceOf(ApiException.class);
        }
        assertThat(call(HttpMethod.POST,base(f)+"/policies",f.user,config(0)).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(catalog.repositories(f.user,f.project,"",100).items()).isEmpty();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_access_audit WHERE action='REPOSITORY_REGISTERED' AND actor=?",Integer.class,f.user)).isZero();
    }

    @Test
    void immutableVersionsAreSerializedAcrossConcurrentPublishers() throws Exception {
        var f=fixture();
        var first=catalog.publish(f.user,f.project,config(100));
        try(var pool=Executors.newFixedThreadPool(4)) {
            var jobs=IntStream.range(0,8).mapToObj(i -> (Callable<Integer>) () -> catalog.publish(f.user,f.project,config(200+i)).versionNumber()).toList();
            var versions=pool.invokeAll(jobs).stream().map(future->{try{return future.get();}catch(Exception e){throw new RuntimeException(e);}}).toList();
            assertThat(versions).containsExactlyInAnyOrder(2,3,4,5,6,7,8,9);
        }
        assertThat(catalog.policy(f.user,f.project,first.id())).isEqualTo(first);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_access_audit WHERE action='POLICY_PUBLISHED' AND actor=?",Integer.class,f.user)).isEqualTo(9);
        jdbc.update("UPDATE platform_policy_version SET config_json='{}' WHERE id=?",first.id());
        assertThatThrownBy(()->catalog.policy(f.user,f.project,first.id())).hasMessageContaining("integrity check failed");
    }

    @Test
    void seekPaginationIsBoundedAndHasNoDuplicates() {
        var f=fixture();
        for(int i=0;i<5;i++) catalog.register(f.user,f.project,"repo"+i,"https://github.com/team/repo"+i);
        var a=catalog.repositories(f.user,f.project,"",2);
        var b=catalog.repositories(f.user,f.project,a.nextCursor(),2);
        var c=catalog.repositories(f.user,f.project,b.nextCursor(),2);
        assertThat(a.items()).hasSize(2); assertThat(b.items()).hasSize(2); assertThat(c.items()).hasSize(1);
        assertThat(c.nextCursor()).isNull();
        assertThat(java.util.stream.Stream.of(a,b,c).flatMap(page->page.items().stream()).map(PlatformCatalogService.Repository::id).distinct()).hasSize(5);
        assertThat(call(HttpMethod.GET,base(f)+"/repositories?limit=101",f.user,null).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(call(HttpMethod.GET,base(f)+"/repositories?limit=abc",f.user,null).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        var organizations=call(HttpMethod.GET,"/api/v1/platform/organizations?limit=1",f.user,null);
        assertThat(organizations.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((List<?>)organizations.getBody().get("items")).hasSize(1);
    }

    @Test
    void duplicateRepositoryDoesNotCreateAnAuditRecord() {
        var f=fixture();
        catalog.register(f.user,f.project,"api","https://github.com/team/api");
        assertThatThrownBy(()->catalog.register(f.user,f.project,"api","https://github.com/team/other")).isInstanceOf(ApiException.class);
        assertThat(catalog.repositories(f.user,f.project,"",100).items()).hasSize(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_access_audit WHERE action='REPOSITORY_REGISTERED' AND actor=?",Integer.class,f.user)).isEqualTo(1);
    }
}
